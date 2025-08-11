from __future__ import annotations

import asyncio
import functools
import inspect
from types import BuiltinFunctionType
from typing import (
    Callable,
    Coroutine,
    Generic,
    ParamSpec,
    Protocol,
    Type,
    TypeVar,
    cast,
    overload,
)

from railtracks.exceptions import NodeCreationError
from railtracks.validation.node_creation.validation import validate_function

from .._node_builder import NodeBuilder
from ..concrete import (
    AsyncDynamicFunctionNode,
    SyncDynamicFunctionNode,
)
from ..manifest import ToolManifest

_TOutput = TypeVar("_TOutput")
_P = ParamSpec("_P")


class _SyncNodeAttachedFunc(Generic[_P, _TOutput], Protocol):
    def __call__(self, *args: _P.args, **kwargs: _P.kwargs) -> _TOutput: ...

    node_type: Type[SyncDynamicFunctionNode[_P, _TOutput]]


class _AsyncNodeAttachedFunc(Generic[_P, _TOutput], Protocol):
    async def __call__(self, *args: _P.args, **kwargs: _P.kwargs) -> _TOutput: ...

    node_type: Type[AsyncDynamicFunctionNode[_P, _TOutput]]


@overload
def function_node(
    func: Callable[_P, Coroutine[None, None, _TOutput]],
    /,
    *,
    name: str | None = None,
    tool_manifest: ToolManifest | None = None,
) -> _AsyncNodeAttachedFunc[_P, _TOutput]:
    pass


@overload
def function_node(
    func: Callable[_P, _TOutput],
    /,
    *,
    name: str | None = None,
    tool_manifest: ToolManifest | None = None,
) -> _SyncNodeAttachedFunc[_P, _TOutput]:
    pass


def function_node(
    func: Callable[_P, Coroutine[None, None, _TOutput] | _TOutput],
    /,
    *,
    name: str | None = None,
    tool_manifest: ToolManifest | None = None,
):
    """
    Creates a new Node type from a function that can be used in `rt.call()`.

    By default, it will parse the function's docstring and turn them into tool details and parameters. However, if
    you provide custom ToolManifest it will override that logic.

    WARNING: If you overriding tool parameters. It is on you to make sure they will work with your function.


    Args:
        func (Callable): The function to convert into a Node.
        name (str, optional): Human-readable name for the node/tool.
        tool_manifest (ToolManifest, optional): The details you would like to override the tool with.
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
        # builtin functions are written in C and do not have space for the addition of metadata like our node type.
        # so instead we wrap them in a function that allows for the addition of the node type.
        # this logic preserved details like the function name, docstring, and signature, but allows us to add the node type.
        func = _function_preserving_metadata(func)
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
        tool_details=tool_manifest.description if tool_manifest is not None else None,
        tool_params=tool_manifest.parameters if tool_manifest is not None else None,
    )

    completed_node_type = builder.build()

    if issubclass(completed_node_type, AsyncDynamicFunctionNode):
        setattr(func, "node_type", completed_node_type)
        return cast(_AsyncNodeAttachedFunc[_P, _TOutput], func)
    elif issubclass(completed_node_type, SyncDynamicFunctionNode):
        setattr(func, "node_type", completed_node_type)
        return cast(_SyncNodeAttachedFunc[_P, _TOutput], func)
    else:
        raise NodeCreationError(
            message="The provided function did not create a valid node type.",
            notes=[
                "This is an unknown bug.",
            ],
        )


def _function_preserving_metadata(
    func: Callable[_P, _TOutput],
):
    @functools.wraps(func)
    def wrapper(*args: _P.args, **kwargs: _P.kwargs) -> _TOutput:
        return func(*args, **kwargs)

    return wrapper
