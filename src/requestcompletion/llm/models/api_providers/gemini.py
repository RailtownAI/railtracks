from ._provider_wrapper import ProviderLLMWrapper


class GeminiLLM(ProviderLLMWrapper):
    def __init__(self, model_name: str, **kwargs):
        provider_name = self.model_type().lower()
        if not model_name.startswith(f"{provider_name}/"):
            model_name = f"{provider_name}/{model_name}"

        # for gemini models through litellm, we need 'gemini/{model_name}' format
        super().__init__(model_name, **kwargs)
    
    @classmethod
    def model_type(cls) -> str:
        return "Gemini"
