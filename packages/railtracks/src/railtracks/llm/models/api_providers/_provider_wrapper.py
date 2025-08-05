from abc import ABC, abstractmethod

import litellm
from litellm.litellm_core_utils.get_llm_provider_logic import get_llm_provider

from .._litellm_wrapper import LiteLLMWrapper
from .._model_exception_base import FunctionCallingNotSupportedError, ModelError


class ProviderLLMWrapper(LiteLLMWrapper, ABC):
    def __init__(self, model_name: str, **kwargs):
        provider_name = self.model_type().lower()
        try:
            # NOTE: Incase of a valid model for gemini, `get_llm_provider` returns provider = vertex_ai.
            model_name = model_name.split("/")[-1]
            provider_info = get_llm_provider(
                model_name
            )  # this function is a little hacky, we are tracking this in issue #379
            assert provider_info[1] == provider_name, (
                f"Provider mismatch. Expected {provider_name}, got {provider_info[1]}"
            )
        except Exception as e:
            reason_str = (
                e.args[0]
                if isinstance(e, AssertionError)
                else f"Please check the model name: {model_name}."
            )
            raise ModelNotFoundError(
                reason=reason_str,
                notes=[
                    "Model name must be a part of the model list.",
                    "Check the model list for the provider you are using.",
                    "Provider List: https://docs.litellm.ai/docs/providers",
                ],
            ) from e

        super().__init__(model_name=self.full_model_name(model_name), **kwargs)

    def full_model_name(self, model_name: str) -> str:
        """After the provider is checked, this method is called to get the full model name"""
        # for anthropic/openai models the full model name is {provider}/{model_name}
        return f"{self.model_type().lower()}/{model_name}"

    @classmethod
    @abstractmethod
    def model_type(cls) -> str:
        """Returns the name of the provider"""
        pass

    def chat_with_tools(self, messages, tools, **kwargs):
        if not litellm.supports_function_calling(model=self._model_name):
            raise FunctionCallingNotSupportedError(self._model_name)
        return super().chat_with_tools(messages, tools, **kwargs)


class ModelNotFoundError(ModelError):
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
