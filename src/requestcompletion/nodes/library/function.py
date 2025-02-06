from __future__ import annotations

from abc import abstractmethod, ABC
from typing import (
    Any,
    TypeVar,
    Callable,
)


from ..nodes import (
    Node,
)


TOutput = TypeVar("_TOutput")

# TODO migrate the following classes to the new system


class FunctionNode(Node[TOutput]):
    """
    A class for ease of creating a function node for the user
    """

    def __init__(self, func: Callable[..., TOutput], **kwargs: dict[str, Any]):
        super().__init__()
        self.func = func
        self.kwargs = kwargs

    def invoke(self) -> TOutput:
        try:
            result = self.func(**self.kwargs)
            if result and isinstance(result, str):
                self.data_streamer(result)

            return result
        except Exception as e:
            raise RuntimeError(f"Error invoking function: {str(e)}")

    def pretty_name(self) -> str:
        return f"Function Node - {self.__class__.__name__}({self.func.__name__})"
