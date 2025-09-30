from ._openai_compatable_provider_wrapper import OpenAICompatibleProviderWrapper

class TelusLLM(OpenAICompatibleProviderWrapper):
    @classmethod
    def model_type(cls) -> str:
        return "Telus"