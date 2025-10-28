from typing import Generic, Literal, TypeVar

from ...providers import ModelProvider
from ._provider_wrapper import ProviderLLMWrapper

_TStream = TypeVar("_TStream", Literal[True], Literal[False])


class OpenAILLM(ProviderLLMWrapper[_TStream], Generic[_TStream]):
    """
    A wrapper that provides access to the OPENAI API.
    """

    @classmethod
    def model_gateway(cls):
        return ModelProvider.OPENAI
