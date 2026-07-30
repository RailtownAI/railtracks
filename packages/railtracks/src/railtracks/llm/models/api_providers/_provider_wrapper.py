from abc import ABC, abstractmethod
from typing import Any, Generic, List, Literal, TypeVar

import litellm
from litellm.litellm_core_utils.get_llm_provider_logic import get_llm_provider

from ...history import MessageHistory
from ...providers import ModelProvider
from ...response import Response
from ...retries.base import RetryApproach
from ...tools import Tool
from .._litellm_wrapper import LiteLLMWrapper
from .._model_exception_base import FunctionCallingNotSupportedError, ModelNotFoundError

_TStream = TypeVar("_TStream", Literal[True], Literal[False])


class ProviderLLMWrapper(LiteLLMWrapper[_TStream], ABC, Generic[_TStream]):
    def __init__(
        self,
        model_name: str,
        stream: _TStream = False,
        api_base: str | None = None,
        api_key: str | None = None,
        temperature: float | None = None,
        top_p: float | None = None,
        max_tokens: int | None = None,
        frequency_penalty: float | None = None,
        presence_penalty: float | None = None,
        reasoning_effort: Literal["minimal", "low", "medium", "high"] | None = None,
        service_tier: str | None = None,
        verbosity: Literal["low", "medium", "high"] | None = None,
        retry_approach: RetryApproach | None = None,
        **kwargs: Any,
    ):
        """Initialize a provider-backed LLM instance.

        Args:
            model_name (str): Name of the model to use, with or without the provider
                prefix (e.g. "gpt-4o" or "openai/gpt-4o").
            stream (bool): Whether to stream the response.
            api_base (str | None, optional): Override the provider's API base URL.
            api_key (str | None, optional): Override the provider's API key.
            temperature (float | None, optional): Sampling temperature. Valid range is
                provider/model-specific (e.g. 0-2 for OpenAI) and enforced server-side,
                not by railtracks.
            top_p (float | None, optional): Nucleus sampling threshold. Same caveat as
                `temperature` on valid range. Anthropic rejects specifying `temperature`
                and `top_p` together on every model tested — use only one.
            max_tokens (int | None, optional): Maximum tokens to generate.
            frequency_penalty (float | None, optional): Penalizes tokens by how often
                they've already appeared. Provider/model-specific support and range.
            presence_penalty (float | None, optional): Penalizes tokens that have
                already appeared at all. Provider/model-specific support and range.
            reasoning_effort (Literal["minimal", "low", "medium", "high"] | None, optional):
                Requested reasoning effort for reasoning-capable models.
            service_tier (str | None, optional): Requested service tier. Provider-specific,
                no railtracks-side enum.
            verbosity (Literal["low", "medium", "high"] | None, optional): Requested
                output verbosity for models that support it (currently OpenAI GPT-5-series,
                excluding Codex variants). Note: at least one provider (OpenAI, confirmed on
                `gpt-5-mini`) silently accepts an invalid value here with no error — pass a
                valid value, don't rely on validation.
            retry_approach (RetryApproach | None, optional): Retry strategy for transient
                failures.
            **kwargs: Any other litellm-supported completion param not named above
                (e.g. `seed`, `logprobs`) — held as-is and merged into every completion
                call. Never checked against `_hyperparameter_support`.

        Raises:
            ModelNotFoundError: If `model_name` doesn't belong to this provider.
            UnsupportedHyperparameterError: If a common hyperparameter above isn't
                supported by the resolved model (per litellm's schema, patched by a
                manual denylist for known-stale cases — see
                `llm/models/_hyperparameter_support.py`).
            MutuallyExclusiveHyperparametersError: If two common hyperparameters can't
                be combined for this provider (currently: Anthropic `temperature` +
                `top_p`).

        Note:
            railtracks does not validate hyperparameter *values* (ranges, types, enum
            members) — invalid values are passed through and will surface as a
            provider-native error (see `verbosity` caveat above for the one known
            exception).
        """
        model_name = self._pre_init_provider_check(model_name)
        super().__init__(
            model_name=self.full_model_name(model_name),
            stream=stream,
            api_base=api_base,
            api_key=api_key,
            temperature=temperature,
            top_p=top_p,
            max_tokens=max_tokens,
            frequency_penalty=frequency_penalty,
            presence_penalty=presence_penalty,
            reasoning_effort=reasoning_effort,
            service_tier=service_tier,
            verbosity=verbosity,
            retry_approach=retry_approach,
            **kwargs,
        )

    def _pre_init_provider_check(self, model_name: str):
        provider_name = self.model_provider().lower()
        try:
            # NOTE: Incase of a valid model for gemini, `get_llm_provider` returns provider = vertex_ai.
            model_name = model_name.split("/")[-1]
            provider_info = get_llm_provider(
                model_name
            )  # this function is a little hacky, we are tracking this in issue #379
            assert provider_info[1] == provider_name, (
                f"Provider mismatch. Expected {provider_name}, got {provider_info[1]}"
            )
            return model_name
        except Exception as e:
            reason_str = (
                e.args[0]
                if isinstance(e, AssertionError)
                else f"Please check the model name: {model_name}."
            )
            raise ModelNotFoundError(
                reason=reason_str,
                notes=[
                    "Model name must be a part of the model list.",
                    "Check the model list for the provider you are using.",
                    "Provider List: https://docs.litellm.ai/docs/providers",
                ],
            ) from e

    def full_model_name(self, model_name: str) -> str:
        """After the provider is checked, this method is called to get the full model name"""
        # for anthropic/openai models the full model name is {provider}/{model_name}
        return f"{self.model_provider().lower()}/{model_name}"

    def model_provider(self) -> ModelProvider:
        """Returns the name of the provider"""
        return self.model_gateway()

    @classmethod
    @abstractmethod
    def model_gateway(cls) -> ModelProvider:
        pass

    def _validate_tool_calling_support(self):
        if not litellm.supports_function_calling(model=self._model_name):
            raise FunctionCallingNotSupportedError(self._model_name)

    def _chat_with_tools(
        self, messages: MessageHistory, tools: List[Tool], **kwargs: Any
    ) -> Response:
        self._validate_tool_calling_support()
        return super()._chat_with_tools(messages, tools, **kwargs)
