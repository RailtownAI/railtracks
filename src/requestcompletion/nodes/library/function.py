from __future__ import annotations

from typing_extensions import Self

from ...llm.tools import Tool

from typing import (
    Any,
    TypeVar,
    Callable,
    List,
    ParamSpec,
    Type,
    Dict,
)


from ..nodes import Node, Tool, Parameter


TOutput = TypeVar("_TOutput")
_P = ParamSpec("_P")


def from_function(func: Callable[[_P], TOutput]) -> Type[Node[TOutput]]:
    """
    A function to create a node from a function
    """

    class DynamicFunctionNode(Node[TOutput]):
        def __init__(self, *args: _P.args, **kwargs: _P.kwargs):
            super().__init__()
            self.args = args
            self.kwargs = kwargs

        def invoke(self) -> TOutput:
            try:
                result = func(*self.args, **self.kwargs)

                return result
            except Exception as e:
                raise RuntimeError(f"Error invoking function: {str(e)}")

        def pretty_name(self) -> str:
            return f"{func.__name__} Node"

        @classmethod
        def tool_info(cls) -> Tool:
            return Tool.from_function(func)

        @classmethod
        def prepare_tool(cls, tool_parameters: Dict[str, Any]) -> Self:
            return cls(**tool_parameters)

    return DynamicFunctionNode


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

    def tool_info(self) -> Tool:
        return self.func

    @classmethod
    def prepare_tool(cls, tool_parameters):
        return cls(**tool_parameters)
