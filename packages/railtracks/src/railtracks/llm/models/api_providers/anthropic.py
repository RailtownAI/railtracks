from ...providers import ModelProvider
from ._provider_wrapper import ProviderLLMWrapper


class AnthropicLLM(ProviderLLMWrapper):
    # litellm's Anthropic transform drops `input_audio` parts, and the API rejects
    # video and other files, so they fail here with a clear error instead.
    _ACCEPTED_MODALITIES = frozenset({"image", "document"})

    @classmethod
    def model_gateway(cls) -> ModelProvider:
        return ModelProvider.ANTHROPIC
