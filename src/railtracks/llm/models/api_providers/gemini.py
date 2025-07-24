from ._provider_wrapper import ProviderLLMWrapper
class GeminiLLM(ProviderLLMWrapper):
    def __init__(self, model_name: str, **kwargs):
        # for gemini models through litellm, we need 'gemini/{model_name}' format, but we do this after the checks in ProiLLMWrapper init
        if not model_name.startswith("gemini/"):
            model_name = f"gemini/{model_name}"

        super().__init__(model_name, **kwargs)

    
    @classmethod
    def model_type(cls) -> str:
        return "Vertex_AI"          # litellm uses this for the provider for Gemini
