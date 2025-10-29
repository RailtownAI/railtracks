from typing import Literal, TypeVar

from ...providers import ModelProvider
from ._provider_wrapper import ProviderLLMWrapper

_TStream = TypeVar("_TStream", Literal[True], Literal[False])


class GeminiLLM(ProviderLLMWrapper):
    def full_model_name(self, model_name: str) -> str:
        # for gemini models through litellm, we need 'gemini/{model_name}' format, but we do this after the checks in ProiLLMWrapper init
        return f"gemini/{model_name}"

    @classmethod
    def model_gateway(cls):
        return ModelProvider.GEMINI  # litellm uses this for the provider for Gemini, we are using this in the checks in _provider_wrapper.py
