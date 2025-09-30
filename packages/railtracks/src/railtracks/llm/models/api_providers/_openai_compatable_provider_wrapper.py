from abc import ABC

from ._provider_wrapper import ProviderLLMWrapper

class OpenAICompatibleProviderWrapper(ProviderLLMWrapper, ABC):

    def __init__(self, model_name: str, api_base: str):
        super().__init__(model_name, api_base=api_base)

    def full_model_name(self, model_name: str) -> str:
        return f"openai/{self.model_type().lower()}/{model_name}"
