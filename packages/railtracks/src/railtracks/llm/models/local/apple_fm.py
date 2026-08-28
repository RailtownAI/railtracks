"""Apple on-device Foundation Model provider.

Wraps Apple's `apple_fm_sdk` (https://github.com/apple/python-apple-fm-sdk) as
a `ModelBase` so users on macOS 26+ Apple Silicon with Apple Intelligence
enabled can drive the system language model through railtracks.

Scope, deliberate:
    - chat, structured output, streaming chat.
    - tool calling raises `NotImplementedError` — Apple's SDK drives its own
      tool loop and exposes no intent-only interception hook, so it does not
      fit railtracks' "return ToolCalls, orchestrate externally" contract.
    - streaming structured output raises — the SDK's `stream_response` does
      not support guided generation.

The SDK exposes no token counts or cost, so `MessageInfo` reports only
`model_name` and measured `latency`; other usage fields are `None`.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, AsyncGenerator, List, Literal, Type

from pydantic import BaseModel

from ...history import MessageHistory
from ...message import (
    AssistantMessage,
    SystemMessage,
    UserMessage,
)
from ...model import ModelBase
from ...providers import ModelProvider
from ...response import MessageInfo, Response
from ...retries.base import RetryApproach
from ...tools import Tool
from ....exceptions.errors import LLMError
from .._model_exception_base import (
    ModelError,
    UnsupportedHyperparameterError,
)

logger = logging.getLogger(__name__)


_APPLE_SUPPORTED_HYPERPARAMS = frozenset(
    {"temperature", "maximum_response_tokens", "sampling_seed"}
)


def _normalize_schema_for_apple(schema: dict) -> dict:
    """Adapt a pydantic JSON schema to what Apple's SDK expects.

    Apple's on-device schema validator requires two things pydantic's
    `model_json_schema()` does not emit:
      - `additionalProperties: false` on every object node.
      - `x-order: <index>` on every property, giving a stable field order.
    Walk the schema and inject both.
    """

    def walk(node):
        if isinstance(node, dict):
            node_type = node.get("type")
            if node_type == "object":
                node.setdefault("additionalProperties", False)
                props = node.get("properties")
                if isinstance(props, dict) and "x-order" not in node:
                    node["x-order"] = list(props.keys())
            elif node_type in {"string", "number", "integer", "boolean"}:
                # Apple treats a titled primitive as a "named type" and
                # then demands enum/other constraints. Drop titles from
                # primitives — the field name is enough.
                node.pop("title", None)
            for v in node.values():
                walk(v)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    walk(schema)
    return schema


class AppleFMUnavailableError(ModelError):
    """Raised when the on-device model is not available on this machine.

    Covers: unsupported OS/hardware, Apple Intelligence disabled, model assets
    not yet downloaded. Surfaced from `AppleFMLLM.__init__`.
    """

    def __init__(self, reason: str):
        super().__init__(reason=reason)


class AppleFMSafetyRefusalError(ModelError):
    """Raised when the on-device model refuses a request on safety grounds.

    Maps `fm.GuardrailViolationError` and `fm.RefusalError` so callers can
    distinguish safety refusals from other model failures.
    """

    def __init__(self, reason: str, message_history: MessageHistory | None = None):
        super().__init__(reason=reason, message_history=message_history)


class AppleFMLLM(ModelBase):
    """Apple's on-device system language model.

    Requires macOS 26+ on Apple Silicon with Apple Intelligence enabled. The
    SDK is installed via `pip install railtracks[apple]`. Inference is
    serialized at the hardware level and runs entirely on-device.

    See the module docstring for the deliberate scope: chat, structured
    output, and streaming chat are supported; tool calling and streaming
    structured output raise `NotImplementedError`.
    """

    def __init__(
        self,
        *,
        use_case: Literal["general", "content_tagging"] = "general",
        temperature: float | None = None,
        maximum_response_tokens: int | None = None,
        sampling_seed: int | None = None,
        guardrails: bool = True,
        retry_approach: RetryApproach | None = None,
        **kwargs: Any,
    ):
        try:
            import apple_fm_sdk as fm
        except ImportError as e:
            raise ImportError(
                "The `apple_fm_sdk` package is required to use AppleFMLLM. "
                "Install with `pip install railtracks[apple]`. Note that the "
                "package itself only runs on macOS 26+ Apple Silicon."
            ) from e

        for k, v in kwargs.items():
            if v is not None:
                raise UnsupportedHyperparameterError(
                    model_name=f"apple-fm-{use_case}", hyperparameter=k, value=v
                )

        super().__init__(retry_approach=retry_approach)

        self._fm = fm
        self._use_case = use_case
        self._guardrails = guardrails
        self._temperature = temperature
        self._maximum_response_tokens = maximum_response_tokens
        self._sampling_seed = sampling_seed

        self._model_handle = self._make_model_handle()
        available, reason = self._model_handle.is_available()
        if not available:
            raise AppleFMUnavailableError(
                f"Apple Foundation Model is not available on this device: {reason}"
            )

    def _make_model_handle(self):
        fm = self._fm
        kwargs: dict[str, Any] = {}
        cases = getattr(fm, "SystemLanguageModelUseCase", None)
        if cases is not None:
            kwargs["use_case"] = getattr(cases, self._use_case.upper(), cases.GENERAL)
        rails = getattr(fm, "SystemLanguageModelGuardrails", None)
        if rails is not None:
            kwargs["guardrails"] = (
                rails.DEFAULT
                if self._guardrails
                else getattr(
                    rails, "PERMISSIVE_CONTENT_TRANSFORMATIONS", rails.DEFAULT
                )
            )
        return fm.SystemLanguageModel(**kwargs)

    def _build_options(self) -> Any | None:
        fm = self._fm
        opts_cls = getattr(fm, "GenerationOptions", None)
        if opts_cls is None:
            return None

        sampling = None
        if self._sampling_seed is not None:
            sampling_cls = getattr(fm, "SamplingMode", None)
            if sampling_cls is not None:
                sampling = sampling_cls.random(seed=self._sampling_seed)

        kwargs: dict[str, Any] = {}
        if sampling is not None:
            kwargs["sampling"] = sampling
        if self._temperature is not None:
            kwargs["temperature"] = self._temperature
        if self._maximum_response_tokens is not None:
            kwargs["maximum_response_tokens"] = self._maximum_response_tokens
        return opts_cls(**kwargs) if kwargs else None

    def model_name(self) -> str:
        return f"apple-fm-{self._use_case}"

    def model_provider(self) -> ModelProvider:
        return ModelProvider.APPLE_FM

    @classmethod
    def model_gateway(cls) -> ModelProvider:
        return ModelProvider.APPLE_FM

    def _split_history(
        self, messages: MessageHistory
    ) -> tuple[str, list, str]:
        """Peel the history into (instructions, prior_turns, final_prompt).

        Apple's session takes `instructions=` once at construction; multi-turn
        context is either implicit (session reuse) or reconstructed via
        `Transcript.from_dict`. We build a fresh session per call, so we hand
        prior turns to `from_transcript` when there are any.
        """
        instructions_parts: list[str] = []
        prior: list = []
        final_prompt: str | None = None

        for msg in messages:
            if isinstance(msg, SystemMessage):
                instructions_parts.append(str(msg.content))
            elif isinstance(msg, UserMessage):
                if final_prompt is not None:
                    prior.append({"role": "user", "contents": [final_prompt]})
                final_prompt = str(msg.content)
            elif isinstance(msg, AssistantMessage):
                prior.append(
                    {"role": "response", "contents": [str(msg.content)]}
                )
            else:
                prior.append({"role": "user", "contents": [str(msg.content)]})

        if final_prompt is None:
            raise LLMError(
                reason="AppleFMLLM requires at least one UserMessage in the history.",
                message_history=messages,
            )

        instructions = "\n\n".join(p for p in instructions_parts if p)
        return instructions, prior, final_prompt

    def _make_session(self, messages: MessageHistory) -> tuple[Any, str]:
        fm = self._fm
        instructions, prior, final_prompt = self._split_history(messages)

        if not prior:
            session = fm.LanguageModelSession(instructions=instructions or None)
            return session, final_prompt

        transcript_entries: list[dict] = []
        if instructions:
            transcript_entries.append(
                {"role": "instructions", "contents": [instructions]}
            )
        transcript_entries.extend(prior)

        transcript_cls = getattr(fm, "Transcript", None)
        from_dict = (
            getattr(transcript_cls, "from_dict", None)
            if transcript_cls is not None
            else None
        )
        from_transcript = getattr(fm.LanguageModelSession, "from_transcript", None)
        if from_dict is not None and from_transcript is not None:
            try:
                transcript = from_dict({"entries": transcript_entries})
                return from_transcript(transcript), final_prompt
            except Exception as e:  # pragma: no cover - depends on installed SDK shape
                logger.warning(
                    "AppleFMLLM: Transcript.from_dict path failed (%s); "
                    "falling back to a single-turn session for this call.",
                    e,
                )

        session = fm.LanguageModelSession(instructions=instructions or None)
        return session, final_prompt

    def extract_message_info(
        self, latency: float | None = None
    ) -> MessageInfo:
        """Populate MessageInfo from what Apple gives us — which is nothing.

        Named to mirror `LiteLLMWrapper.extract_message_info` so the two files
        read the same. `total_cost` is left `None` to match how other
        providers report missing usage; on-device inference is genuinely
        free but reporting `0.0` would silently conflate "free" with
        "unknown" in mixed-provider aggregations.
        """
        return MessageInfo(
            input_tokens=None,
            output_tokens=None,
            latency=latency,
            model_name=self.model_name(),
            total_cost=None,
            system_fingerprint=None,
        )

    def _prepare_response(self, content: Any, latency: float) -> Response:
        return Response(
            AssistantMessage(content),
            self.extract_message_info(latency=latency),
        )

    def _translate_fm_error(
        self, e: BaseException, messages: MessageHistory
    ) -> ModelError:
        fm = self._fm
        safety = tuple(
            cls
            for name in ("GuardrailViolationError", "RefusalError")
            if (cls := getattr(fm, name, None)) is not None
        )
        if safety and isinstance(e, safety):
            return AppleFMSafetyRefusalError(
                reason=f"Apple Foundation Model refused the request: {e}",
                message_history=messages,
            )
        unavailable = getattr(fm, "AssetsUnavailableError", None)
        if unavailable is not None and isinstance(e, unavailable):
            return AppleFMUnavailableError(
                f"Apple Foundation Model assets unavailable: {e}"
            )
        return LLMError(reason=str(e), message_history=messages)

    def _run_sync(self, coro):
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(coro)
        coro.close()
        raise ModelError(
            reason=(
                "AppleFMLLM sync API cannot be called from inside a running "
                "event loop. Use achat / astructured / astream_chat instead."
            )
        )

    def _chat(self, messages: MessageHistory) -> Response:
        return self._run_sync(self._achat(messages))

    def _structured(
        self, messages: MessageHistory, schema: Type[BaseModel]
    ) -> Response:
        return self._run_sync(self._astructured(messages, schema))

    def _chat_with_tools(
        self, messages: MessageHistory, tools: List[Tool]
    ) -> Response:
        raise NotImplementedError(
            "AppleFMLLM does not support tool calling. Apple's on-device SDK "
            "drives the tool loop internally and provides no intent-only "
            "interception hook, so it does not fit railtracks' external "
            "orchestration contract. Use OpenAI/Anthropic/Ollama for "
            "tool-driven flows."
        )

    async def _achat(self, messages: MessageHistory) -> Response:
        session, prompt = self._make_session(messages)
        opts = self._build_options()
        start = time.time()
        try:
            if opts is not None:
                text = await session.respond(prompt, options=opts)
            else:
                text = await session.respond(prompt)
        except self._fm.FoundationModelsError as e:
            raise self._translate_fm_error(e, messages) from e
        return self._prepare_response(str(text), latency=time.time() - start)

    async def _astructured(
        self, messages: MessageHistory, schema: Type[BaseModel]
    ) -> Response:
        session, prompt = self._make_session(messages)
        opts = self._build_options()
        json_schema = _normalize_schema_for_apple(schema.model_json_schema())
        start = time.time()
        try:
            if opts is not None:
                result = await session.respond(
                    prompt, json_schema=json_schema, options=opts
                )
            else:
                result = await session.respond(prompt, json_schema=json_schema)
        except self._fm.FoundationModelsError as e:
            raise self._translate_fm_error(e, messages) from e

        parsed = self._parse_structured(result, schema, messages)
        return self._prepare_response(parsed, latency=time.time() - start)

    def _parse_structured(
        self,
        result: Any,
        schema: Type[BaseModel],
        messages: MessageHistory,
    ) -> BaseModel:
        to_json = getattr(result, "to_json", None)
        raw = to_json() if callable(to_json) else str(result)
        try:
            return schema.model_validate_json(raw)
        except Exception as e:
            raise LLMError(
                reason=(
                    f"AppleFMLLM structured output did not match schema "
                    f"{schema.__name__}: {e}"
                ),
                message_history=messages,
            ) from e

    async def _achat_with_tools(
        self, messages: MessageHistory, tools: List[Tool]
    ) -> Response:
        raise NotImplementedError(
            "AppleFMLLM does not support tool calling. Apple's on-device SDK "
            "drives the tool loop internally and provides no intent-only "
            "interception hook, so it does not fit railtracks' external "
            "orchestration contract. Use OpenAI/Anthropic/Ollama for "
            "tool-driven flows."
        )

    async def _astream_chat(
        self, messages: MessageHistory
    ) -> AsyncGenerator[str | Response, None]:
        session, prompt = self._make_session(messages)
        opts = self._build_options()
        prev = ""
        start = time.time()
        try:
            if opts is not None:
                stream = session.stream_response(prompt, options=opts)
            else:
                stream = session.stream_response(prompt)
            async for snapshot in stream:
                text = str(snapshot)
                delta = text[len(prev):]
                prev = text
                if delta:
                    yield delta
        except self._fm.FoundationModelsError as e:
            raise self._translate_fm_error(e, messages) from e

        yield self._prepare_response(prev, latency=time.time() - start)

    async def _astream_chat_with_tools(
        self, messages: MessageHistory, tools: List[Tool]
    ) -> AsyncGenerator[str | Response, None]:
        raise NotImplementedError(
            "AppleFMLLM does not support tool calling; streaming with tools "
            "is therefore also unavailable."
        )
        yield  # pragma: no cover - marks this as an async generator

    async def _astream_structured(
        self,
        messages: MessageHistory,
        schema: Type[BaseModel],
    ) -> AsyncGenerator[str | Response, None]:
        raise NotImplementedError(
            "AppleFMLLM does not support streaming structured output. "
            "Apple's `stream_response` does not accept guided generation. "
            "Use `astructured` for buffered structured output."
        )
        yield  # pragma: no cover - marks this as an async generator
