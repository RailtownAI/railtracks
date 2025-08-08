from abc import ABC, abstractmethod
from typing import Any, List

import litellm
from litellm.litellm_core_utils.get_llm_provider_logic import get_llm_provider

from ...history import MessageHistory
from ...response import Response
from ...tools import Tool
from .._litellm_wrapper import LiteLLMWrapper
from .._model_exception_base import FunctionCallingNotSupportedError, ModelError


class ProviderLLMWrapper(LiteLLMWrapper, ABC):
    def __init__(self, model_name: str, **kwargs):
        model_name = self._pre_init_provider_check(model_name)
        super().__init__(model_name=self.full_model_name(model_name), **kwargs)

    def _pre_init_provider_check(self, model_name: str):
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
            return model_name
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

    def full_model_name(self, model_name: str) -> str:
        """After the provider is checked, this method is called to get the full model name"""
        # for anthropic/openai models the full model name is {provider}/{model_name}
        return f"{self.model_type().lower()}/{model_name}"

    @classmethod
    @abstractmethod
    def model_type(cls) -> str:
        """Returns the name of the provider"""
        pass

    def _chat_with_tools(
        self, messages: MessageHistory, tools: List[Tool], **kwargs: Any
    ) -> Response:
        # NOTE: special exception case for higgingface
        # Due to the wide range of huggingface models, `litellm.supports_function_calling` isn't always accurate.
        # so we are just going to skip the check and the error (if any) will be generated at runtime during `litellm.completion`.
        if (
            not self.model_type() == "HuggingFace"
            and not litellm.supports_function_calling(model=self._model_name)
        ):
            raise FunctionCallingNotSupportedError(self._model_name)
        return super()._chat_with_tools(messages, tools, **kwargs)


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
