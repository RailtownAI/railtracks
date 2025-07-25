from ._provider_wrapper import ProviderLLMWrapper


class OpenAILLM(ProviderLLMWrapper):
    """
    A wrapper that provides access to the OPENAI API.
    """

    @classmethod
    def model_type(cls) -> str:
        return "OpenAI"
    
    def full_model_name(self, model_name: str) -> str:
        # for openai models the full model name is openai/{model_name}
        # we don't necessarily need this, but it is here for consistency
        if not model_name.startswith("openai/"):
            model_name = f"{self.model_type().lower()}/{model_name}"
