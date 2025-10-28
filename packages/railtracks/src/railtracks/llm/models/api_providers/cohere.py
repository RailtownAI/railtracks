from ...providers import ModelProvider
from ._provider_wrapper import ProviderLLMWrapper


class CohereLLM(ProviderLLMWrapper):
    """
    A wrapper that provides access to the Cohere API.
    """

    @classmethod
    def model_gateway(cls):
        return ModelProvider.COHERE
