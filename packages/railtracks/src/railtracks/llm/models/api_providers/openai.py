from ._provider_wrapper import ProviderLLMWrapper


class OpenAILLM(ProviderLLMWrapper):
    """
    A wrapper that provides access to the OPENAI API.
    """

    @classmethod
    def model_type(cls) -> str:
        return "OpenAI"
