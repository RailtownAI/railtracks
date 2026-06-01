from __future__ import annotations

import asyncio
import functools
import inspect
import warnings
from types import BuiltinFunctionType
from typing import Any, Callable, Coroutine, Generic, List, ParamSpec, Protocol, TypeVar, overload

from railtracks.built_nodes._node_builder import NodeBuilder

from railtracks.built_nodes.concrete.function_base import RTFunction
from railtracks.exceptions import NodeCreationError
from railtracks.nodes.manifest import ToolManifest
from railtracks.nodes.nodes import Node
from railtracks.state.node import NodeForest
from railtracks.validation.node_creation.validation import (
    validate_function,
    validate_tool_manifest_against_function,
)

_TOutput = TypeVar("_TOutput")
_P = ParamSpec("_P")
    
class CallableSyncRTFunction(RTFunction[_P, _TOutput], Protocol, Generic[_P, _TOutput]):
    def __call__(self, *args: _P.args, **kwargs: _P.kwargs) -> _TOutput: ...

class CallableAsyncRTFunction(RTFunction[_P, _TOutput], Protocol, Generic[_P, _TOutput]):
    async def __call__(self, *args: _P.args, **kwargs: _P.kwargs) -> _TOutput: ...

@overload
def function_node(
    func: Callable[_P, Coroutine[None, None, _TOutput]],
    /,
    *,
    name: str | None = None,
    manifest: ToolManifest | None = None,
) -> CallableAsyncRTFunction[_P, _TOutput]: ...


@overload
def function_node(
    func: Callable[_P, _TOutput],
    /,
    *,
    name: str | None = None,
    manifest: ToolManifest | None = None,
) -> CallableSyncRTFunction[_P, _TOutput]:
    pass


@overload
def function_node(
    func: List[Callable[..., Any]],
    /,
    *,
    name: str | None = None,
    manifest: ToolManifest | None = None,
) -> List[RTFunction[..., Any]]:
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


def _single_function_node(
    func: Callable[_P, Coroutine[None, None, _TOutput] | _TOutput],
    /,
    *,
    name: str | None = None,
    manifest: ToolManifest | None = None,
) -> CallableSyncRTFunction[_P, _TOutput] | CallableAsyncRTFunction[_P, _TOutput]:
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
        assert isinstance(func.node_type, Node), "The provided function has a node_type attribute but it is not a Node. This unexpected behavior"
        return func

    if not isinstance(
        func, BuiltinFunctionType
    ):  # we don't require dict validation for builtin functions, that is handled separately.
        validate_function(func)  # checks for dict or Dict parameters

    # Validate tool manifest against function signature if manifest is provided
    if manifest is not None:
        validate_tool_manifest_against_function(func, manifest.parameters)

    if inspect.isbuiltin(func):
        # builtin functions are written in C and do not have space for the addition of metadata like our node type.
        # so instead we wrap them in a function that allows for the addition of the node type.
        # this logic preserved details like the function name, docstring, and signature, but allows us to add the node type.
        func = _function_preserving_metadata(func)

    elif not asyncio.iscoroutinefunction(func) and not inspect.isfunction(func):
        raise NodeCreationError(
            message=f"The provided function is not a valid coroutine or sync function it is {type(func)}.",
            notes=[
                "You must provide a valid function or coroutine function to make a node.",
            ],
        )

    unwrapped_func: Callable[_P, Coroutine[None, None, _TOutput]]
    if not asyncio.iscoroutinefunction(func):
        async def wrapped_function(*args: _P.args, **kwargs: _P.kwargs) -> _TOutput:
            return await asyncio.to_thread(func, *args, **kwargs)

        unwrapped_func = wrapped_function
    else:
        unwrapped_func = func


    builder = NodeBuilder().function(
        unwrapped_func,
        name=name if name is not None else f"{unwrapped_func.__name__}",
        tool_details=manifest.description if manifest is not None else None,
        tool_params=manifest.parameters if manifest is not None else None,
    )

    completed_node_type = builder.build()

    if issubclass(completed_node_type, Node):
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
    else:
        return _single_function_node(func, name=name, manifest=manifest)



def _function_preserving_metadata(
    func: Callable[_P, _TOutput],
) -> Callable[_P, _TOutput]:
    """
    Wraps the given function in a trivial wrapper that preserves its metadata.
    """

    @functools.wraps(func)
    def wrapper(*args: _P.args, **kwargs: _P.kwargs) -> _TOutput:
        return func(*args, **kwargs)

    return wrapper
