from ...providers import ModelProvider
from ._provider_wrapper import ProviderLLMWrapper


class AnthropicLLM(ProviderLLMWrapper):
    @classmethod
    def model_gateway(cls) -> ModelProvider:
        return ModelProvider.ANTHROPIC
