from abc import ABC

import litellm
from litellm.litellm_core_utils.get_llm_provider_logic import get_llm_provider

from ....exceptions.errors import LLMError
from .._litellm_wrapper import LiteLLMWrapper


class ProviderLLMWrapper(LiteLLMWrapper, ABC):
    def __init__(self, model_name: str, **kwargs):
        provider_name = self.model_type().lower()
        provider_info = get_llm_provider(model_name)
        # Check if the model name is valid
        if provider_info[1] != provider_name:
            raise LLMError(
                reason=f"Invalid model name: {model_name}. Model name must be a part of {provider_name}'s model list.",
            )
        super().__init__(model_name=model_name, **kwargs)

    def chat_with_tools(self, messages, tools, **kwargs):
        if not litellm.supports_function_calling(model=self._model_name):
            raise LLMError(
                reason=f"Model {self._model_name} does not support function calling. Chat with tools is not supported."
            )
        return super().chat_with_tools(messages, tools, **kwargs)
