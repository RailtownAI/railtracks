from ._provider_wrapper import ProviderLLMWrapper
from ..providers import ModelProvider

class AnthropicLLM(ProviderLLMWrapper):
    @classmethod
    def model_type(cls):
        return ModelProvider.ANTHROPIC
