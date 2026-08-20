from __future__ import annotations

import asyncio
import json
import mimetypes
import threading
import time
from abc import ABC
from json import JSONDecodeError
from typing import (
    Any,
    AsyncGenerator,
    Callable,
    Dict,
    Generator,
    Iterable,
    List,
    Literal,
    Tuple,
    Type,
    TypeVar,
    cast,
    overload,
)

import litellm
from litellm.litellm_core_utils.streaming_handler import CustomStreamWrapper
from litellm.types.utils import (
    ChatCompletionMessageToolCall,
    Function,
    ModelResponse,
    ModelResponseStream,
)
from pydantic import BaseModel, Field

from ...exceptions.errors import LLMError, NodeInvocationError
from ..content import ToolCall, ToolCalls
from ..history import MessageHistory
from ..message import AssistantMessage, Message, ToolMessage, UserMessage
from ..model import ModelBase
from ..response import MessageInfo, Response
from ..retries import RetryApproach
from ..tools import Tool
from ..tools.parameters import Parameter
from ._hyperparameter_support import (
    default_reasoning_effort_for_tools,
    find_mutually_exclusive_conflict,
    is_hyperparameter_supported,
)
from ._model_exception_base import (
    MutuallyExclusiveHyperparametersError,
    UnsupportedHyperparameterError,
)

_TBaseModel = TypeVar("_TBaseModel", bound=BaseModel)

# Sentinel marking normal end-of-stream on the sync→async bridge queue (see
# `_bridge_sync_stream` / `_pump_sync_stream`). A dedicated object avoids colliding with any
# legitimate streamed value.
_STREAM_DONE = object()

# Dropped unsupported parameters from the request to the model.
litellm.drop_params = True
litellm.modify_params = True

# this flag is only used in two places in litellm
# https://github.com/search?q=repo%3ABerriAI%2Flitellm%20suppress_debug_info&type=code
litellm.suppress_debug_info = True


def _process_single_parameter(p: Parameter) -> tuple[str, Dict[str, Any], bool]:
    """
    Process a single parameter and return (name, prop_dict, is_required).
    We now just defer entirely to each Parameter instance's .to_json_schema() method.
    """
    prop_dict = p.to_json_schema()
    return p.name, prop_dict, p.required


def _handle_set_of_parameters(
    parameters: List[Parameter],
    sub_property: bool = False,
) -> Dict[str, Any]:
    """
    Handle a set of Parameter instances and convert to JSON schema.
    If sub_property is True, returns just the properties dict, else return full schema.
    """
    props: Dict[str, Any] = {}
    required: list[str] = []

    for p in parameters:
        name, prop_dict, is_required = _process_single_parameter(p)
        props[name] = prop_dict
        if is_required:
            required.append(name)

    if sub_property:
        return props
    else:
        schema = {
            "type": "object",
            "properties": props,
        }
        if required:
            schema["required"] = required
        return schema


def _parameters_to_json_schema(
    parameters: List[Parameter] | None,
) -> Dict[str, Any]:
    """
    Turn a set of Parameter instances
    into a JSON Schema dict accepted by litellm.completion.
    """
    if parameters is None:
        return {}

    if isinstance(parameters, Iterable) and all(
        isinstance(x, Parameter) for x in parameters
    ):
        return _handle_set_of_parameters(list(parameters))

    raise NodeInvocationError(
        message=f"Unable to parse Tool.parameters. It was {parameters}",
        fatal=True,
        notes=[
            "Tool.parameters must be a set of Parameter objects",
        ],
    )


def _model_in_litellm_catalog(model_name: str) -> bool:
    """True if litellm has capability metadata for this model name.

    Custom deployment names (Azure Foundry etc.) route through litellm but
    have no entry in the capability catalog, so any `supports_*` probe on
    them returns False regardless of what the underlying model can actually
    do. This helper lets callers distinguish "litellm knows the answer is
    False" from "litellm has no idea, don't trust the probe."
    """
    if model_name in litellm.model_cost:
        return True
    try:
        routed_model, _, _, _ = litellm.get_llm_provider(model=model_name)
    except Exception:
        return False
    return routed_model in litellm.model_cost


def _to_litellm_tool(tool: Tool) -> Dict[str, Any]:
    """
    Convert your Tool object into the dict format for litellm.completion.
    """
    # parameters may be None
    json_schema = _parameters_to_json_schema(tool.parameters)
    litellm_tool = {
        "type": "function",
        "function": {
            "name": tool.name,
            "description": tool.detail,
            "parameters": json_schema,
        },
    }
    return litellm_tool


class StreamedToolCall(BaseModel):
    tool: ToolCall
    args: str | None = Field(default=None)  # accumulating string of arguments (in json)

    def load_args(self):
        try:
            self.tool.arguments = json.loads(self.args) if self.args else {}
        except JSONDecodeError as e:
            raise ValueError(
                f"Failed to decode tool call arguments: {str(e)}",
            )


class LiteLLMWrapper(ModelBase, ABC):
    """
    A large base class that wraps around a litellm model.

    Note that the model object should be interacted with via the methods provided in the wrapper class:
    - `chat`
    - `structured`
    - `chat_with_tools`
    - `astream_chat` (and the other `astream_*` per-call streaming methods)

    Each individual API should implement the required `abstract_methods` in order to allow users to interact with a
    model of that type.
    """

    _COMMON_HYPERPARAMETERS = (
        "temperature",
        "top_p",
        "max_tokens",
        "frequency_penalty",
        "presence_penalty",
        "reasoning_effort",
        "service_tier",
        "verbosity",
    )

    def __init__(
        self,
        model_name: str,
        api_base: str | None = None,
        api_key: str | None = None,
        temperature: float | None = None,
        top_p: float | None = None,
        max_tokens: int | None = None,
        frequency_penalty: float | None = None,
        presence_penalty: float | None = None,
        reasoning_effort: Literal["none", "minimal", "low", "medium", "high"]
        | None = None,
        service_tier: str | None = None,
        verbosity: Literal["low", "medium", "high"] | None = None,
        retry_approach: RetryApproach | None = None,
        **kwargs: Any,
    ):
        """Initialize the litellm-backed model wrapper.

        Most callers construct a provider subclass (e.g. `rt.llm.OpenAILLM`) instead of
        this base class directly; see `ProviderLLMWrapper.__init__` for the full
        per-hyperparameter description of the common hyperparameters below (`top_p`,
        `max_tokens`, `frequency_penalty`, `presence_penalty`, `reasoning_effort`,
        `service_tier`, `verbosity`) and their known provider gotchas.

        Raises:
            UnsupportedHyperparameterError: If a common hyperparameter isn't supported
                by `model_name` (per litellm's schema or the manual denylist in
                `llm/models/_hyperparameter_support.py`).
            MutuallyExclusiveHyperparametersError: If two common hyperparameters can't
                be combined for this provider (currently: Anthropic `temperature` +
                `top_p`).

        Note:
            No client-side validation of hyperparameter *values* is performed —
            invalid values are passed through as-is and surface as a provider-native
            error, except `verbosity`, which at least one provider (OpenAI) silently
            accepts even when invalid.
        """
        super().__init__(retry_approach=retry_approach)
        self._model_name = model_name
        self.api_base = api_base
        self.api_key = api_key
        self.temperature = temperature
        self.top_p = top_p
        self.max_tokens = max_tokens
        self.frequency_penalty = frequency_penalty
        self.presence_penalty = presence_penalty
        self.reasoning_effort = reasoning_effort
        self.service_tier = service_tier
        self.verbosity = verbosity
        self._extra_completion_kwargs = kwargs
        self._validate_common_hyperparameter_support()

    def _validate_common_hyperparameter_support(self) -> None:
        provider = (
            self.model_provider().lower() if hasattr(self, "model_provider") else None
        )
        if provider is None:
            return
        for name in self._COMMON_HYPERPARAMETERS:
            value = getattr(self, name)
            if value is not None and not is_hyperparameter_supported(
                self._model_name, provider, name
            ):
                raise UnsupportedHyperparameterError(self._model_name, name, value)

        hyperparameters_set = frozenset(
            name
            for name in self._COMMON_HYPERPARAMETERS
            if getattr(self, name) is not None
        )
        conflict = find_mutually_exclusive_conflict(provider, hyperparameters_set)
        if conflict:
            raise MutuallyExclusiveHyperparametersError(
                self._model_name,
                sorted(conflict),
                {name: getattr(self, name) for name in conflict},
            )

    def _base_completion_kwargs(self) -> Dict[str, Any]:
        """Common kwargs shared by both `_invoke` and `_ainvoke`, merged in only if set."""
        kwargs: Dict[str, Any] = dict(self._extra_completion_kwargs)
        for name in (
            "api_base",
            "api_key",
            "temperature",
            "top_p",
            "max_tokens",
            "frequency_penalty",
            "presence_penalty",
            "reasoning_effort",
            "service_tier",
            "verbosity",
        ):
            value = getattr(self, name)
            if value is not None:
                kwargs[name] = value
        return kwargs

    @overload
    def _invoke(
        self,
        messages: MessageHistory,
        *,
        response_format: Any | None = ...,
        tools: list[Tool] | None = ...,
        stream: Literal[True],
    ) -> Tuple[CustomStreamWrapper, float]: ...

    @overload
    def _invoke(
        self,
        messages: MessageHistory,
        *,
        response_format: Any | None = ...,
        tools: list[Tool] | None = ...,
        stream: Literal[False] = ...,
    ) -> Tuple[ModelResponse, float]: ...

    def _invoke(
        self,
        messages: MessageHistory,
        *,
        response_format: Any | None = None,
        tools: list[Tool] | None = None,
        stream: bool = False,
    ) -> Tuple[CustomStreamWrapper | ModelResponse, float]:
        """
        Internal helper that:
          1. Converts MessageHistory
          2. Merges default kwargs
          3. Calls litellm.completion

        This is a *blocking* call. Streaming rides litellm's synchronous
        `completion(stream=True)` API (bridged onto the event loop by `_bridge_sync_stream`);
        run it in a worker thread (e.g. `asyncio.to_thread`) from async contexts.

        Args:
            messages: The message history to send to the model.
            response_format: An optional response format (e.g. a pydantic schema).
            tools: The tools to make available to the model, if any.

        Returns:
            A `(completion, time)` tuple. When `stream=True`, `completion` is a
            `CustomStreamWrapper` and `time` is the request start time; when `stream=False`,
            `completion` is a `ModelResponse` and `time` is the completion latency. The
            overloads narrow the return type from the `stream` literal.
        """
        start_time = time.time()
        litellm_messages = [self._to_litellm_message(m) for m in messages]
        merged = self._base_completion_kwargs()

        if response_format is not None:
            merged["response_format"] = response_format

        if tools is not None:
            litellm_tools = [_to_litellm_tool(t) for t in tools]
            merged["tools"] = litellm_tools

        effective_reasoning_effort = default_reasoning_effort_for_tools(
            self._model_name,
            merged.get("reasoning_effort"),
            has_tools=tools is not None,
        )
        if effective_reasoning_effort is not None:
            merged["reasoning_effort"] = effective_reasoning_effort

        def completion_function():
            return litellm.completion(
                model=self._model_name,
                messages=litellm_messages,
                stream=stream,
                **merged,
            )

        if self.retry_approach is not None:
            completion = self.retry_approach.call_with_retry(completion_function)
        else:
            completion = completion_function()

        if isinstance(completion, CustomStreamWrapper):
            return completion, start_time
        else:
            completion_time = time.time() - start_time
            return completion, completion_time

    # ================ START Streaming Handlers ===============
    async def _bridge_sync_stream(
        self,
        make_stream: Callable[[], Generator[str | Response, None, Response]],
    ) -> AsyncGenerator[str | Response, None]:
        """
        Run a *blocking* sync stream on a dedicated worker thread and surface its items as an
        async generator, without blocking the event loop.

        litellm's synchronous `completion(stream=True)` is better maintained than its async
        counterpart (the async path is prone to leaking noisy logs/warnings), so railtracks
        streams on the sync API and bridges the blocking iterator here. A single worker thread
        owns the underlying network stream for its whole lifetime — it is created, iterated,
        and closed on that one thread, so the stream object is never touched from more than one
        thread — while items are handed to the event loop through a thread-safe queue.

        Args:
            make_stream: A zero-arg factory (run *on the worker thread*) that opens the request
                and returns the sync `_stream_handler_base` generator of `str` chunks followed
                by a final `Response`.

        Yields:
            str | Response: `str` chunks as they arrive, then the terminal `Response`.
        """
        loop = asyncio.get_running_loop()
        queue: asyncio.Queue[Any] = asyncio.Queue()
        stop = threading.Event()

        worker = asyncio.ensure_future(
            asyncio.to_thread(self._pump_sync_stream, make_stream, loop, queue, stop)
        )
        try:
            while True:
                item = await queue.get()
                if item is _STREAM_DONE:
                    break
                if isinstance(item, BaseException):
                    raise item
                yield cast("str | Response", item)
        finally:
            # On early break, signal the worker to stop; it observes `stop` at the next chunk
            # boundary, closes the stream on its own thread, and exits. Retrieve its result so
            # a late failure isn't reported as "exception never retrieved".
            stop.set()
            if worker.done():
                worker.exception()
            else:
                worker.add_done_callback(lambda t: t.exception())

    @staticmethod
    def _pump_sync_stream(
        make_stream: Callable[[], Generator[str | Response, None, Response]],
        loop: asyncio.AbstractEventLoop,
        queue: asyncio.Queue[Any],
        stop: threading.Event,
    ) -> None:
        """Worker-thread half of `_bridge_sync_stream`.

        Opens, iterates, and closes the blocking stream entirely on the calling thread (so the
        network stream object is never touched from more than one thread), marshaling each item
        or a terminal `_STREAM_DONE` / exception  back to the loop thread via `queue`.
        """
        try:
            gen = make_stream()
        except BaseException as exc:  # noqa: BLE001 - marshaled to the consumer
            loop.call_soon_threadsafe(queue.put_nowait, exc)
            return
        try:
            for item in gen:
                loop.call_soon_threadsafe(queue.put_nowait, item)
                if stop.is_set():
                    break
        except BaseException as exc:  # noqa: BLE001 - marshaled to the consumer
            loop.call_soon_threadsafe(queue.put_nowait, exc)
        else:
            loop.call_soon_threadsafe(queue.put_nowait, _STREAM_DONE)
        finally:
            gen.close()

    def _stream_handler_base(
        self,
        raw: CustomStreamWrapper,
        start_time: float,
        output_schema: Type[_TBaseModel] | None = None,
    ) -> Generator[Response | str, None, Response]:
        """
        Intercepts the given stream wrapper and provides a new generator.
        The generator should iterate and provide strings cluminating in the last response being a Response object

        """
        tools: List[ToolCall] = []
        accumulated_content = ""

        # fall back on empty message info if we don't get one from the stream.
        message_info = MessageInfo()
        active_tool_calls: Dict[int, StreamedToolCall] = {}
        stream_finished = False

        for chunk in raw:
            if stream_finished:
                # the last chunk will contain the full message info. Note this only true for openai. Anthropic is known to not.

                message_info = self.extract_message_info(
                    chunk, time.time() - start_time
                )

                break

            choice = chunk.choices[0]

            if self._is_stream_finished(choice):
                stream_finished = True
                tools = self._finalize_remaining_tool_calls(active_tool_calls)
                continue

            if choice.delta.tool_calls:
                self._handle_tool_call_delta(
                    choice.delta.tool_calls[0], active_tool_calls
                )

            elif choice.delta.content:
                content = self._handle_content_delta(choice.delta.content)
                accumulated_content += content
                yield content

        r = self._prepare_response(
            accumulated_content=accumulated_content,
            tools=tools,
            output_schema=output_schema,
            message_info=message_info,
        )

        yield r
        return r

    def _prepare_response(
        self,
        *,
        accumulated_content: str,
        tools: list[ToolCall],
        output_schema: type[BaseModel] | None,
        message_info: MessageInfo,
    ):
        """
        From the provided content, creates a completes a response object dyanmically.

        This function handles the normalization of the different response `content` types.
        """
        structured_response: BaseModel | None = None

        if output_schema is not None:
            structured_response = output_schema(**json.loads(accumulated_content))

        if structured_response is not None:
            r = Response(
                message=AssistantMessage(content=structured_response),
                message_info=message_info,
            )
        elif len(tools) > 0:
            r = Response(
                message=AssistantMessage(
                    content=ToolCalls(tools, text=accumulated_content or None)
                ),
                message_info=message_info,
            )
        else:
            r = Response(
                message=AssistantMessage(content=accumulated_content),
                message_info=message_info,
            )

        return r

    def _is_stream_finished(self, choice) -> bool:
        """Check if the stream has finished."""
        return choice.finish_reason in ("stop", "tool_calls")

    def _finalize_remaining_tool_calls(
        self, active_tool_calls: dict[int, StreamedToolCall]
    ) -> list[ToolCall]:
        """

        Finalize any remaining active tool calls and return them.

        """
        tools: list[ToolCall] = []
        for tool_data in active_tool_calls.values():
            if tool_data.args is not None:
                tool_data.load_args()
            tools.append(tool_data.tool)

        return tools

    def _handle_tool_call_delta(
        self, call, active_tool_calls: dict[int, StreamedToolCall]
    ):
        """Process a tool call delta from the stream."""
        call_index = getattr(call, "index", 0)

        if call.id:  # New tool call starting
            self._start_new_tool_call(call, call_index, active_tool_calls)
        else:  # Continue streaming arguments
            self._continue_tool_call_arguments(call, call_index, active_tool_calls)

    def _start_new_tool_call(
        self, call, call_index: int, active_tool_calls: dict[int, StreamedToolCall]
    ):
        """Start a new tool call, finalizing any previous one at the same index."""
        # Finalize previous tool call at this index if exists
        if call_index in active_tool_calls:
            prev_data = active_tool_calls[call_index]
            if prev_data.args:
                prev_data.tool.arguments = json.loads(prev_data.args)

        # Start new tool call
        active_tool_calls[call_index] = StreamedToolCall(
            tool=ToolCall(identifier=call.id, name=call.function.name, arguments={}),
            args="",
        )

    def _continue_tool_call_arguments(
        self, call, call_index: int, active_tool_calls: dict[int, StreamedToolCall]
    ):
        """Continue accumulating arguments for an existing tool call."""
        if call_index in active_tool_calls and call.function.arguments:
            active_tool_calls[call_index].args += call.function.arguments

    def _handle_content_delta(self, content) -> str:
        """Process content delta and return validated content string."""
        assert isinstance(content, str), "Content is not string"
        return content or ""

    # ================ END Streaming Handlers ===============

    # ================ START Per-call Streaming LLM calls ===============
    # These implement the ModelBase._astream_* extension points. Each one requests a streamed
    # response and returns an async generator yielding `str` chunks followed by a single final
    # `Response`. They ride litellm's synchronous `completion(stream=True)` API, bridged onto the
    # event loop by `_bridge_sync_stream` (a dedicated worker thread), so the loop never blocks.

    async def _astream_chat(self, messages: MessageHistory):
        def _open() -> Generator[str | Response, None, Response]:
            raw, start_time = self._invoke(messages, stream=True)
            assert isinstance(raw, CustomStreamWrapper), (
                f"did not return streamed response, instead {type(raw)}"
            )
            return self._stream_handler_base(raw, start_time)

        async for item in self._bridge_sync_stream(_open):
            yield item

    async def _astream_chat_with_tools(
        self, messages: MessageHistory, tools: List[Tool]
    ):
        def _open() -> Generator[str | Response, None, Response]:
            raw, start_time = self._invoke(messages, tools=tools, stream=True)
            assert isinstance(raw, CustomStreamWrapper), (
                f"did not return streamed response, instead {type(raw)}"
            )
            return self._stream_handler_base(raw, start_time)

        async for item in self._bridge_sync_stream(_open):
            yield item

    async def _astream_structured(
        self, messages: MessageHistory, schema: Type[BaseModel]
    ):
        def _open() -> Generator[str | Response, None, Response]:
            raw, start_time = self._invoke(
                messages, response_format=schema, stream=True
            )
            assert isinstance(raw, CustomStreamWrapper), (
                f"did not return streamed response, instead {type(raw)}"
            )
            return self._stream_handler_base(raw, start_time, schema)

        async for item in self._bridge_sync_stream(_open):
            yield item

    # ================ END Per-call Streaming LLM calls ===============

    # ================ START Base Handlers ==================

    def _chat_handle_base(self, raw: ModelResponse, info: MessageInfo):
        content = raw["choices"][0]["message"]["content"]
        return Response(message=AssistantMessage(content=content), message_info=info)

    def _structured_handle_base(
        self,
        raw: ModelResponse,
        info: MessageInfo,
        schema: Type[BaseModel],
    ) -> Response:
        content_str = raw["choices"][0]["message"]["content"]
        parsed = schema(**json.loads(content_str))
        return Response(message=AssistantMessage(content=parsed), message_info=info)

    def _chat_with_tools_handler_base(
        self, raw: ModelResponse, info: MessageInfo
    ) -> Response:
        """
        Handle the response from litellm.completion when using tools.
        """
        choice = raw.choices[0]

        if choice.finish_reason == "stop" and not choice.message.tool_calls:
            # litellm types content as str | None, but a plain "stop" completion always
            # carries (possibly empty) text content.
            return Response(
                message=AssistantMessage(content=cast(str, choice.message.content)),
                message_info=info,
            )

        calls: List[ToolCall] = []
        for tc in choice.message.tool_calls or []:
            args = json.loads(tc.function.arguments)
            calls.append(
                ToolCall(identifier=tc.id, name=tc.function.name or "", arguments=args)
            )

        # Keep any text the model returned alongside the tool calls (e.g. "I will
        # check the weather in London for you"), it is part of the answer.
        assistant_msg = AssistantMessage(
            content=ToolCalls(calls, text=choice.message.content)
        )

        # Preserve the raw litellm message so that provider-specific metadata
        # (e.g. Gemini thought_signature) is round-tripped back verbatim.
        assistant_msg.raw_litellm_message = choice.message
        return Response(message=assistant_msg, message_info=info)

    # ================ END Base Handlers ===============

    # ================ START Sync LLM calls ===============

    def _chat(self, messages: MessageHistory) -> Response:
        response, time = self._invoke(messages=messages)
        return self._chat_handle_base(
            response, self.extract_message_info(response, time)
        )

    def _structured(
        self, messages: MessageHistory, schema: Type[BaseModel]
    ) -> Response:
        try:
            model_resp, time = self._invoke(messages, response_format=schema)
            return self._structured_handle_base(
                model_resp,
                self.extract_message_info(model_resp, time),
                schema,
            )
        except JSONDecodeError as jde:
            raise jde
        except Exception as e:
            raise LLMError(
                reason="Structured LLM call failed",
                message_history=messages,
            ) from e

    def _chat_with_tools(self, messages: MessageHistory, tools: List[Tool]) -> Response:
        """
        Chat with the model using tools.

        Args:
            messages: The message history to use as context
            tools: The tools to make available to the model

        Returns:
            A Response containing either plain assistant text or ToolCall(s).
        """
        resp, time = self._invoke(messages, tools=tools)
        return self._chat_with_tools_handler_base(
            resp, self.extract_message_info(resp, time)
        )

    # ================ END Sync LLM calls ===============

    # ================ START Async LLM calls ===============
    # litellm's async API (`acompletion`) is intentionally not used: its sync counterpart is
    # better maintained and does not leak the noisy logs/warnings the async path is prone to.
    # The async surface is preserved by running the blocking sync calls on a worker thread
    # (`asyncio.to_thread`), exactly as the framework's buffered node path already does.

    async def _achat(self, messages: MessageHistory) -> Response:
        return await asyncio.to_thread(self._chat, messages)

    async def _astructured(
        self, messages: MessageHistory, schema: Type[BaseModel]
    ) -> Response:
        return await asyncio.to_thread(self._structured, messages, schema)

    async def _achat_with_tools(
        self, messages: MessageHistory, tools: List[Tool]
    ) -> Response:
        return await asyncio.to_thread(self._chat_with_tools, messages, tools)

    # ================ END Async LLM calls ===============

    def __str__(self) -> str:
        parts = self._model_name.split("/", 1)
        if len(parts) == 2:
            return f"LiteLLMWrapper(provider={parts[0]}, name={parts[1]})"
        return f"LiteLLMWrapper(name={self._model_name})"

    def model_name(self) -> str:
        """
        Returns the model name.
        """
        return self._model_name

    def _to_litellm_message(self, msg: Message) -> Dict[str, Any]:
        """
        Convert your Message (UserMessage, AssistantMessage, ToolMessage) into
        the simple dict format that litellm.completion expects.
        """
        base: Dict[str, Any] = {"role": msg.role}
        # handle the special case where the message is a tool so we have to link it to the tool id.
        if isinstance(msg, UserMessage) and msg.attachment is not None:
            # Initiate content list with text component
            content_list: List[Dict[str, Any]] = [{"type": "text", "text": msg.content}]

            # Add attachments (images or documents)
            for msg_attachment in msg.attachment:
                url = (
                    msg_attachment.encoding
                    if msg_attachment.encoding is not None
                    else msg_attachment.url
                )
                if msg_attachment.modality == "document":
                    # Only trust litellm's PDF-support check when the model is in
                    # litellm's capability catalog. Custom deployment names (Azure
                    # Foundry etc.) route fine but have no capability metadata,
                    # so supports_pdf_input returns False by default and would
                    # falsely reject valid deployments. When the model isn't in
                    # the catalog, skip the pre-check and let the API decide.
                    if _model_in_litellm_catalog(
                        self._model_name
                    ) and not litellm.utils.supports_pdf_input(self._model_name):
                        raise ValueError(
                            f"Model {self._model_name!r} does not support PDF attachments. "
                            "Use a PDF-capable model or render the PDF pages to images first."
                        )
                    fallback_ext = (
                        mimetypes.guess_extension(msg_attachment.mime_type or "") or ""
                    )
                    content_list.append(
                        {
                            "type": "file",
                            "file": {
                                "file_data": url,
                                "filename": msg_attachment.filename
                                or f"attachment{fallback_ext}",
                            },
                        }
                    )
                else:
                    content_list.append(
                        {
                            "type": "image_url",
                            "image_url": {"url": url},
                        }
                    )

            base["content"] = content_list

        elif isinstance(msg, ToolMessage):
            base["name"] = msg.content.name
            base["tool_call_id"] = msg.content.identifier
            base["content"] = msg.content.result
        # only time this is true is tool calls, need to return litellm.utils.Message
        elif isinstance(msg.content, list):
            assert all(isinstance(t_c, ToolCall) for t_c in msg.content)
            # Send back any text that came with the tool calls so the model sees
            # its own full turn on the next request.
            base["content"] = getattr(msg.content, "text", None) or ""
            base["tool_calls"] = [
                ChatCompletionMessageToolCall(
                    function=Function(
                        arguments=tool_call.arguments, name=tool_call.name
                    ),
                    id=tool_call.identifier,
                    type="function",
                )
                for tool_call in msg.content
            ]
            # Copy provider-specific metadata (e.g. Gemini thought_signature)
            # from the raw litellm message without returning it wholesale,
            # since msg.content may have been truncated and returning the raw
            # message would re-introduce tool_call_ids that lack responses.
            raw = getattr(msg, "raw_litellm_message", None)
            if raw is not None:
                _standard_fields = {
                    "role",
                    "content",
                    "tool_calls",
                    "function_call",
                    "name",
                }
                raw_dict = (
                    raw
                    if isinstance(raw, dict)
                    else vars(raw)
                    if hasattr(raw, "__dict__")
                    else {}
                )
                for key, value in raw_dict.items():
                    if key not in _standard_fields and value is not None:
                        base[key] = value
        else:
            base["content"] = msg.content
        return base

    @classmethod
    def extract_message_info(
        cls, model_response: ModelResponse | ModelResponseStream, latency: float
    ) -> MessageInfo:
        """
        Create a Response object from a ModelResponse.

        Args:
            model_response (ModelResponse): The response from the model.
            latency (float): The latency of the response in seconds.

        Returns:
            MessageInfo: An object containing the details about the message info.
        """
        # litellm does not statically type these attributes (usage/_hidden_params are set
        # dynamically), so we go through Any; _return_none_on_error absorbs absent fields.
        raw: Any = model_response
        input_tokens = _return_none_on_error(lambda: raw.usage.prompt_tokens)
        output_tokens = _return_none_on_error(lambda: raw.usage.completion_tokens)
        model_name = _return_none_on_error(lambda: raw.model)
        system_fingerprint = _return_none_on_error(lambda: raw.system_fingerprint)
        total_cost = _return_none_on_error(lambda: raw._hidden_params["response_cost"])

        return MessageInfo(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            latency=latency,
            model_name=model_name,
            total_cost=total_cost,
            system_fingerprint=system_fingerprint,
        )


_T = TypeVar("_T")


def _return_none_on_error(func: Callable[[], _T]) -> _T | None:
    try:
        return func()
    except:  # noqa: E722
        return None
