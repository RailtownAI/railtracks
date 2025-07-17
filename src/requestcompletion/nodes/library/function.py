from __future__ import annotations

import asyncio
import inspect
from types import BuiltinFunctionType
from typing import (
    Callable,
    Coroutine,
)

import typing_extensions

from .easy_usage_wrappers.node_builder import NodeBuilder
from .function_base import _TOutput, _P, SyncDynamicFunctionNode, AsyncDynamicFunctionNode
from ...exceptions import NodeCreationError
from ...exceptions.node_creation.validation import validate_function
from ...llm.tools import Tool
from ..nodes import Node


def to_node(func):
    """Decorator to convert a function into a Node using from_function."""
    return from_function(func)


def from_function(
    func: Callable[[_P], Coroutine[None, None, _TOutput] | _TOutput],
    /,
    *,
    pretty_name: str | None = None,
):
    """
    Creates a new Node type from a function that can be used in `rc.call()`.
    """

    if not isinstance(
        func, BuiltinFunctionType
    ):  # we don't require dict validation for builtin functions, that is handled separately.
        validate_function(func)  # checks for dict or Dict parameters
    else:
        raise RuntimeError(
            "Cannot convert kwargs for builtin functions. "
            "Please use a custom function."
        )

    if asyncio.iscoroutinefunction(func):
        type_ = AsyncDynamicFunctionNode
    elif inspect.isfunction(func):
        type_ = SyncDynamicFunctionNode
    else:
        raise NodeCreationError(
            message="The provided function is not a valid coroutine or sync function.",
            notes=[
                "You must provide a valid function or coroutine function to make a node.",
            ],
        )

    builder = NodeBuilder(
        type_,
        pretty_name=pretty_name if pretty_name is not None else f"{func.__name__} Node",
    )

    builder.setup_function_node(func)

    return builder.build()


@typing_extensions.deprecated(
    "The function node is deprecated use DynamicFunctionNode instead."
)
class FunctionNode(Node[_TOutput]):
    """
    A class for ease of creating a function node for the user
    """

    def __init__(
        self,
        func: Callable[[_P], Coroutine[None, None, _TOutput] | _TOutput],
        *args: _P.args,
        **kwargs: _P.kwargs,
    ):
        super().__init__()
        self.func = func
        self.args = args
        self.kwargs = kwargs

    async def invoke(self) -> _TOutput:
        result = self.func(*self.args, **self.kwargs)
        if asyncio.iscoroutine(self.func):
            await result

        return result

    @classmethod
    def pretty_name(cls) -> str:
        return f"Function Node - {cls.__class__.__name__}"

    @classmethod
    def tool_info(cls) -> Tool:
        return Tool.from_function(cls.func)

    @classmethod
    def prepare_tool(cls, tool_parameters):
        return cls(**tool_parameters)
