from __future__ import annotations

import asyncio
import inspect
from types import BuiltinFunctionType
from typing import (
    Callable,
    Coroutine,
    Set,
)

from requestcompletion.exceptions import NodeCreationError
from requestcompletion.exceptions.node_creation.validation import validate_function
from requestcompletion.llm import Parameter
from requestcompletion.nodes._node_builder import NodeBuilder
from requestcompletion.nodes.library.function_base import (
    _P,
    AsyncDynamicFunctionNode,
    SyncDynamicFunctionNode,
    _TOutput,
)


def to_node(func):
    """Decorator to convert a function into a Node using from_function."""
    return from_function(func)


def from_function(
    func: Callable[[_P], Coroutine[None, None, _TOutput] | _TOutput],
    /,
    *,
    pretty_name: str | None = None,
    tool_details: str | None = None,
    tool_params: dict | Set[Parameter] | None = None,
):
    """
    Creates a new Node type from a function that can be used in `rc.call()`.

    By default, it will parse the function's parameters and turn them into tool details and parameters. However, if
    you provide custom tool details or parameters, they will override the defaults.

    Args:
        func (Callable): The function to convert into a Node.
        pretty_name (str, optional): Human-readable name for the node/tool.
        tool_details (str, optional): Description of the node subclass for other LLMs to know how to use this as a tool.
        tool_params (dict or Set[Parameter], optional): Parameters that must be passed if other LLMs want to use this as a tool.
    """

    if not isinstance(
        func, BuiltinFunctionType
    ):  # we don't require dict validation for builtin functions, that is handled separately.
        validate_function(func)  # checks for dict or Dict parameters

    if asyncio.iscoroutinefunction(func):
        type_ = AsyncDynamicFunctionNode
    elif inspect.isfunction(func):
        type_ = SyncDynamicFunctionNode
    elif inspect.isbuiltin(func):
        type_ = SyncDynamicFunctionNode
    else:
        raise NodeCreationError(
            message=f"The provided function is not a valid coroutine or sync function it is {type(func)}.",
            notes=[
                "You must provide a valid function or coroutine function to make a node.",
            ],
        )

    builder = NodeBuilder(
        type_,
        pretty_name=pretty_name,
    )

    builder.setup_function_node(
        func,
        tool_details=tool_details,
        tool_params=tool_params,
    )

    return builder.build()
