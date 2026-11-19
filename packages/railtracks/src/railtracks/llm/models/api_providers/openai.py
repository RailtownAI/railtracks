from ...providers import ModelProvider
from ._provider_wrapper import ProviderLLMWrapper


class OpenAILLM(ProviderLLMWrapper):
    """
    A wrapper that provides access to the OPENAI API.
    """

    # Audio is sent as `input_audio`, which OpenAI's audio models accept.
    _ACCEPTED_MODALITIES = frozenset({"image", "document", "audio"})

    @classmethod
    def model_gateway(cls):
        return ModelProvider.OPENAI
