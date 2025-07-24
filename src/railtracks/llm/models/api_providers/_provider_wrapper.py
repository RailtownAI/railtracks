from abc import ABC

import litellm
from litellm.litellm_core_utils.get_llm_provider_logic import get_llm_provider

from ....exceptions.errors import LLMError
from .._litellm_wrapper import LiteLLMWrapper


class ProviderLLMWrapper(LiteLLMWrapper, ABC):
    def __init__(self, model_name: str, **kwargs):
        provider_name = self.model_type().lower()
        try:
            _model_name = model_name.split("/")[-1]          # incase the model name is in the format of provider/model_name
            provider_info = get_llm_provider(_model_name)
        except Exception as e:
            raise ModelNotFoundError(
                reason=f"Please check the model name: {model_name}.",
                notes=[
                    "Model name must be a part of the model list.",
                    "Check the model list for the provider you are using.",
                    "Provider List: https://docs.litellm.ai/docs/providers",
                ],
            ) from e    
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


class ModelNotFoundError(LLMError):
    def __init__(self, reason: str, notes: list[str] = None):
        self.reason = reason
        self.notes = notes or []
        super().__init__(reason)

    def __str__(self):
        base = super().__str__()
        if self.notes:
            notes_str = (
                "\n"
                + self._color("Tips to debug:\n", self.GREEN)
                + "\n".join(self._color(f"- {note}", self.GREEN) for note in self.notes)
            )
            return f"\n{self._color(base, self.RED)}{notes_str}"
        return self._color(base, self.RED)
