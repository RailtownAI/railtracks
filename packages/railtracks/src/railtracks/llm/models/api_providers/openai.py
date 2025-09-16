from ._provider_wrapper import ProviderLLMWrapper
from ..providers import ModelProvider


class OpenAILLM(ProviderLLMWrapper):
    """
    A wrapper that provides access to the OPENAI API.
    """

    @classmethod
    def model_type(cls):
        return ModelProvider.OPENAI
