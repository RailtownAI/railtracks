from ..providers import ModelProvider
from ._provider_wrapper import ProviderLLMWrapper


class AnthropicLLM(ProviderLLMWrapper):
    @classmethod
    def model_type(cls):
        return ModelProvider.ANTHROPIC
