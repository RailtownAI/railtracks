from __future__ import annotations

import asyncio
import functools
import inspect
import warnings
from types import BuiltinFunctionType
from typing import Callable, Coroutine, List, ParamSpec, TypeVar, overload

from railtracks.built_nodes._node_builder import NodeBuilder
from railtracks.built_nodes.concrete import (
    AsyncDynamicFunctionNode,
    RTAsyncFunction,
    RTSyncFunction,
    SyncDynamicFunctionNode,
)
from railtracks.exceptions import NodeCreationError
from railtracks.nodes.manifest import ToolManifest
from railtracks.validation.node_creation.validation import (
    validate_function,
    validate_tool_manifest_against_function,
)

_TOutput = TypeVar("_TOutput")
_P = ParamSpec("_P")


@overload
def function_node(
    func: Callable[_P, Coroutine[None, None, _TOutput]],
    /,
    *,
    name: str | None = None,
    manifest: ToolManifest | None = None,
) -> RTAsyncFunction[_P, _TOutput]:
    pass


@overload
def function_node(
    func: Callable[_P, _TOutput],
    /,
    *,
    name: str | None = None,
    manifest: ToolManifest | None = None,
) -> RTSyncFunction[_P, _TOutput]:
    pass


@overload
def function_node(
    func: List[Callable[_P, Coroutine[None, None, _TOutput] | _TOutput]],
    /,
    *,
    name: str | None = None,
    manifest: ToolManifest | None = None,
) -> List[RTAsyncFunction[_P, _TOutput] | RTSyncFunction[_P, _TOutput]]:
    pass


def validate_function_parameters(
    func: Callable[_P, Coroutine[None, None, _TOutput] | _TOutput],
    manifest: ToolManifest | None = None,
):
    """
    Validates that the parameters of the function are valid for use in a node.
    """
    if hasattr(func, "node_type"):
        warnings.warn(
            "The provided function has already been converted to a node.",
            UserWarning,
        )
        return func

    if not isinstance(
        func, BuiltinFunctionType
    ):  # we don't require dict validation for builtin functions, that is handled separately.
        validate_function(func)  # checks for dict or Dict parameters

    # Validate tool manifest against function signature if manifest is provided
    if manifest is not None:
        validate_tool_manifest_against_function(func, manifest.parameters)


def function_node_(
    func: Callable[_P, Coroutine[None, None, _TOutput] | _TOutput]
    | List[Callable[_P, Coroutine[None, None, _TOutput] | _TOutput]],
    /,
    *,
    name: str | None = None,
    manifest: ToolManifest | None = None,
):
    """
    Creates a new Node type from a function that can be used in `rt.call()`.

    By default, it will parse the function's docstring and turn them into tool details and parameters. However, if
    you provide custom ToolManifest it will override that logic.

    WARNING: If you overriding tool parameters. It is on you to make sure they will work with your function.

    NOTE: If you have already converted this function to a node this function will do nothing

    Args:
        func (Callable): The function to convert into a Node.
        name (str, optional): Human-readable name for the node/tool.
        manifest (ToolManifest, optional): The details you would like to override the tool with.
    """

    if hasattr(func, "node_type"):
        warnings.warn(
            "The provided function has already been converted to a node.",
            UserWarning,
        )
        return func

    if not isinstance(
        func, BuiltinFunctionType
    ):  # we don't require dict validation for builtin functions, that is handled separately.
        validate_function(func)  # checks for dict or Dict parameters

    # Validate tool manifest against function signature if manifest is provided
    if manifest is not None:
        validate_tool_manifest_against_function(func, manifest.parameters)

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
        tool_details=manifest.description if manifest is not None else None,
        tool_params=manifest.parameters if manifest is not None else None,
    )

    completed_node_type = builder.build()

    # there is some pretty scary logic here.
    if issubclass(completed_node_type, AsyncDynamicFunctionNode):
        setattr(func, "node_type", completed_node_type)
        return func
    elif issubclass(completed_node_type, SyncDynamicFunctionNode):
        setattr(func, "node_type", completed_node_type)
        return func
    else:
        raise NodeCreationError(
            message="The provided function did not create a valid node type.",
            notes=[
                "Please make a github issue with the details of what went wrong.",
            ],
        )


def function_node(
    func: Callable[_P, Coroutine[None, None, _TOutput] | _TOutput]
    | List[Callable[_P, Coroutine[None, None, _TOutput] | _TOutput]],
    /,
    *,
    name: str | None = None,
    manifest: ToolManifest | None = None,
) -> (
    Callable[_P, Coroutine[None, None, _TOutput] | _TOutput]
    | List[Callable[_P, Coroutine[None, None, _TOutput] | _TOutput]]
    | None
):
    """
    Creates a new Node type from a function that can be used in `rt.call()`.

    By default, it will parse the function's docstring and turn them into tool details and parameters. However, if
    you provide custom ToolManifest it will override that logic.

    WARNING: If you overriding tool parameters. It is on you to make sure they will work with your function.

    NOTE: If you have already converted this function to a node this function will do nothing

    Args:
        func (Callable): The function to convert into a Node.
        name (str, optional): Human-readable name for the node/tool.
        manifest (ToolManifest, optional): The details you would like to override the tool with.
    """

    # handle the case where a list of functions is provided
    if isinstance(func, list):
        return [function_node(f, name=name, manifest=manifest) for f in func]

    # check if the function has already been converted to a node
    if hasattr(func, "node_type"):
        warnings.warn(
            "The provided function has already been converted to a node.",
            UserWarning,
        )
        return func

    # validate_function_parameters is separated out to allow for easier testing.
    validate_function_parameters(func, manifest)

    # assign the correct node class based on whether the function is async or sync
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

    # build the node using the NodeBuilder
    builder = NodeBuilder(
        node_class,
        name=name if name is not None else f"{func.__name__}",
    )

    builder.setup_function_node(
        func,
        tool_details=manifest.description if manifest is not None else None,
        tool_params=manifest.parameters if manifest is not None else None,
    )

    completed_node_type = builder.build()

    # there is some pretty scary logic here.
    if issubclass(completed_node_type, AsyncDynamicFunctionNode):
        setattr(func, "node_type", completed_node_type)
        return func
    elif issubclass(completed_node_type, SyncDynamicFunctionNode):
        setattr(func, "node_type", completed_node_type)
        return func
    else:
        raise NodeCreationError(
            message="The provided function did not create a valid node type.",
            notes=[
                "Please make a github issue with the details of what went wrong.",
            ],
        )


def _function_preserving_metadata(
    func: Callable[_P, _TOutput],
):
    """
    Wraps the given function in a trivial wrapper that preserves its metadata.
    """

    @functools.wraps(func)
    def wrapper(*args: _P.args, **kwargs: _P.kwargs) -> _TOutput:
        return func(*args, **kwargs)

    return wrapper
