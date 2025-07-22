from .provider_wrapper import ProviderLLMWrapper


class AnthropicLLM(ProviderLLMWrapper):
    @classmethod
    def model_type(cls) -> str:
        return "Anthropic"
