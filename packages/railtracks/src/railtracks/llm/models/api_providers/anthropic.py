from typing import Generic, Literal, TypeVar

from ...providers import ModelProvider
from ._provider_wrapper import ProviderLLMWrapper

_TStream = TypeVar("_TStream", Literal[True], Literal[False])


class AnthropicLLM(ProviderLLMWrapper[_TStream], Generic[_TStream]):
    @classmethod
    def model_gateway(cls) -> ModelProvider:
        return ModelProvider.ANTHROPIC
