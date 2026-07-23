from abc import ABC
from typing import Literal, TypeVar

from ...providers import ModelProvider, ReasoningEffort
from ...retries import RetryApproach
from ._provider_wrapper import ProviderLLMWrapper

_TStream = TypeVar("_TStream", Literal[True], Literal[False])


class OpenAICompatibleProvider(ProviderLLMWrapper[_TStream], ABC):
    def __init__(
        self,
        model_name: str,
        *,
        stream: _TStream = False,
        api_base: str,
        api_key: str,
        temperature: float | None = None,
        top_p: float | None = None,
        max_tokens: int | None = None,
        frequency_penalty: float | None = None,
        presence_penalty: float | None = None,
        reasoning_effort: ReasoningEffort | str | None = None,
        service_tier: str | None = None,
        verbosity: Literal["low", "medium", "high"] | str | None = None,
        retry_approach: RetryApproach | None = None,
    ):
        super().__init__(
            model_name,
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
        )

    def full_model_name(self, model_name: str) -> str:
        return f"openai/{model_name}"

    @classmethod
    def model_gateway(cls) -> ModelProvider:
        return ModelProvider.UNKNOWN

    def _pre_init_provider_check(self, model_name: str):
        # For OpenAI compatible providers, we skip the provider check since there is no way to do it.
        return model_name

    def _validate_tool_calling_support(self):
        # For OpenAI compatible providers, we skip the tool calling support check since there is no way to do it.
        return

    def _validate_common_param_support(self) -> None:
        # For OpenAI compatible providers, litellm can't reliably introspect
        # gateway-style providers, so we skip the common param support check.
        return
