from abc import ABC

from ...providers import ModelProvider
from ...retries import RetryApproach
from ._provider_wrapper import ProviderLLMWrapper


class OpenAICompatibleProvider(ProviderLLMWrapper, ABC):
    def __init__(
        self,
        model_name: str,
        *,
        api_base: str,
        api_key: str,
        temperature: float | None = None,
        retry_approach: RetryApproach | None = None,
    ):
        super().__init__(
            model_name,
            api_base=api_base,
            api_key=api_key,
            temperature=temperature,
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
