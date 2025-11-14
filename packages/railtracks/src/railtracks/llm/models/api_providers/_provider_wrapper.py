from abc import ABC, abstractmethod
from typing import Any, Generic, List, Literal, TypeVar

import litellm
from litellm.litellm_core_utils.get_llm_provider_logic import get_llm_provider

from ...history import MessageHistory
from ...providers import ModelProvider
from ...response import Response
from ...tools import Tool
from .._litellm_wrapper import LiteLLMWrapper
from .._model_exception_base import FunctionCallingNotSupportedError, ModelNotFoundError

_TStream = TypeVar("_TStream", Literal[True], Literal[False])


class ProviderLLMWrapper(LiteLLMWrapper[_TStream], ABC, Generic[_TStream]):
    def __init__(
        self,
        model_name: str,
        stream: _TStream = False,
        api_base: str | None = None,
        api_key: str | None = None,
    ):
        model_name = self._pre_init_provider_check(model_name)
        super().__init__(
            model_name=self.full_model_name(model_name),
            stream=stream,
            api_base=api_base,
            api_key=api_key,
        )

    def _pre_init_provider_check(self, model_name: str):
        provider_name = self.model_provider().lower()
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
        return f"{self.model_provider().lower()}/{model_name}"

    def model_provider(self) -> ModelProvider:
        """Returns the name of the provider"""
        return self.model_gateway()

    @classmethod
    @abstractmethod
    def model_gateway(cls) -> ModelProvider:
        pass

    def _validate_tool_calling_support(self):
        if not litellm.supports_function_calling(model=self._model_name):
            raise FunctionCallingNotSupportedError(self._model_name)

    def _chat_with_tools(
        self, messages: MessageHistory, tools: List[Tool], **kwargs: Any
    ) -> Response:
        self._validate_tool_calling_support()
        return super()._chat_with_tools(messages, tools, **kwargs)
