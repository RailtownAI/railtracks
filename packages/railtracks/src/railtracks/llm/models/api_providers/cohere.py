from ._provider_wrapper import ProviderLLMWrapper


class CohereLLM(ProviderLLMWrapper):
    """
    A wrapper that provides access to the Cohere API.
    """

    @classmethod
    def model_type(cls) -> str:
        return "cohere_chat"
