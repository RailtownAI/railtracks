from __future__ import annotations

import asyncio
import inspect
from types import BuiltinFunctionType
from typing import (
    Callable,
    Coroutine,
    ParamSpec,
    Set,
    Type,
    TypeVar,
    overload,
)

from railtracks.exceptions import NodeCreationError
from railtracks.llm import Parameter
from railtracks.validation.node_creation.validation import validate_function

from .._node_builder import NodeBuilder
from ..concrete import (
    AsyncDynamicFunctionNode,
    SyncDynamicFunctionNode,
)

_TOutput = TypeVar("_TOutput")
_P = ParamSpec("_P")


@overload
def function_node(
    func: Callable[_P, Coroutine[None, None, _TOutput]],
    /,
    *,
    name: str | None = None,
    tool_details: str | None = None,
    tool_params: set[Parameter] | None = None,
) -> Type[AsyncDynamicFunctionNode[_P, _TOutput]]:
    pass


@overload
def function_node(
    func: Callable[_P, _TOutput],
    /,
    *,
    name: str | None = None,
    tool_details: str | None = None,
    tool_params: set[Parameter] | None = None,
) -> Type[SyncDynamicFunctionNode[_P, _TOutput]]:
    pass


def function_node(
    func: Callable[_P, Coroutine[None, None, _TOutput] | _TOutput],
    /,
    *,
    name: str | None = None,
    tool_details: str | None = None,
    tool_params: dict | Set[Parameter] | None = None,
):
    """
    Creates a new Node type from a function that can be used in `rt.call()`.

    By default, it will parse the function's parameters and turn them into tool details and parameters. However, if
    you provide custom tool details or parameters, they will override the defaults.

    Args:
        func (Callable): The function to convert into a Node.
        name (str, optional): Human-readable name for the node/tool.
        tool_details (str, optional): Description of the node subclass for other LLMs to know how to use this as a tool.
        tool_params (dict or Set[Parameter], optional): Parameters that must be passed if other LLMs want to use this as a tool.
    """

    if not isinstance(
        func, BuiltinFunctionType
    ):  # we don't require dict validation for builtin functions, that is handled separately.
        validate_function(func)  # checks for dict or Dict parameters

    if asyncio.iscoroutinefunction(func):
        node_class = AsyncDynamicFunctionNode
    elif inspect.isfunction(func):
        node_class = SyncDynamicFunctionNode
    elif inspect.isbuiltin(func):
        node_class = SyncDynamicFunctionNode
    else:
        raise NodeCreationError(
            message=f"The provided function is not a valid coroutine or sync function it is {type(func)}.",
            notes=[
                "You must provide a valid function or coroutine function to make a node.",
            ],
        )

    builder = NodeBuilder(
        node_class,
        name=name if name is not None else f"{func.__name__}",
    )

    builder.setup_function_node(
        func,
        tool_details=tool_details,
        tool_params=tool_params,
    )

    return builder.build()
