from __future__ import annotations

import warnings
import asyncio
import functools
import inspect
from types import BuiltinFunctionType
from typing import (
    Callable,
    Coroutine,
    Iterable,
    List,
    ParamSpec,
    TypeVar,
    cast,
    overload,
)

from railtracks.built_nodes.function.base import RTFunction
from railtracks.exceptions import NodeCreationError
from railtracks.middleware.core import Middleware
from railtracks.nodes.manifest import ToolManifest
from railtracks.nodes.nodes import Node
from railtracks.validation.node_creation.validation import (
    validate_function,
    validate_tool_manifest_against_function,
)

from .base import CallableAsyncRTFunction, CallableSyncRTFunction
from .node_builder import FunctionNodeBuilder

_TOutput = TypeVar("_TOutput")
_P = ParamSpec("_P")


# note there is an intentional overlap in overloads
# by running the first overload check it will pick up all `async` functions
# this avoid python's inability to distinguish between `async` and `sync` functions in overloads
@overload
def function_node(  # pyright: ignore[reportOverlappingOverload]
    func: Callable[_P, Coroutine[None, None, _TOutput]],
    /,
    *,
    name: str | None = None,
    manifest: ToolManifest | None = None,
    middleware: Iterable[Middleware[_P, _TOutput]] | None = None,
) -> CallableAsyncRTFunction[_P, _TOutput]: ...


@overload
def function_node(
    func: Callable[_P, _TOutput],
    /,
    *,
    name: str | None = None,
    manifest: ToolManifest | None = None,
    middleware: Iterable[Middleware[_P, _TOutput]] | None = None,
) -> CallableSyncRTFunction[_P, _TOutput]:
    pass


@overload
def function_node(
    func: List[Callable],
    /,
    *,
    name: str | None = None,
    manifest: ToolManifest | None = None,
    middleware: Iterable[Middleware] | None = None,
) -> List[CallableAsyncRTFunction | CallableSyncRTFunction]:
    pass


@overload
def function_node(
    func: None = None,
    /,
    *,
    name: str | None = None,
    manifest: ToolManifest | None = None,
    middleware: Iterable[Middleware[_P, _TOutput]] | None = None,
) -> Callable[
    [Callable[_P, Coroutine[None, None, _TOutput]] | Callable[_P, _TOutput]],
    RTFunction[_P, _TOutput],
]:
    pass


def validate_function_parameters(
    func: Callable[_P, Coroutine[None, None, _TOutput]] | Callable[_P, _TOutput],
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


# intentional overload overlap, as in `function_node` above: async is checked first
@overload
def _validate_and_normalize_callable(  # pyright: ignore[reportOverlappingOverload]
    func: Callable[_P, Coroutine[None, None, _TOutput]],
    manifest: ToolManifest | None,
) -> Callable[_P, Coroutine[None, None, _TOutput]]: ...


@overload
def _validate_and_normalize_callable(
    func: Callable[_P, _TOutput],
    manifest: ToolManifest | None,
) -> Callable[_P, _TOutput]: ...


def _validate_and_normalize_callable(
    func: Callable[_P, Coroutine[None, None, _TOutput]] | Callable[_P, _TOutput],
    manifest: ToolManifest | None,
) -> Callable[_P, Coroutine[None, None, _TOutput]] | Callable[_P, _TOutput]:
    """Validate ``func`` and normalise it into a node-ready callable.

    Resolves partial metadata, validates parameters against an optional
    ``manifest``, wraps builtins, and rejects unsupported callables. Overloaded so
    the sync/async character of ``func`` is preserved in the return type.

    Args:
        func: The callable to validate and normalise.
        manifest: Optional tool manifest to validate against ``func``'s signature.

    Returns:
        A callable equivalent to ``func`` that is safe to hand to the node builder.

    Raises:
        NodeCreationError: If ``func`` is not a supported callable type.
    """
    # partials lack real __name__/__qualname__/__doc__; recover them onto a copy
    if isinstance(func, functools.partial):
        func = _partial_with_resolved_metadata(func)

    # dict-parameter validation; builtins are validated separately
    if not isinstance(func, BuiltinFunctionType):
        validate_function(func)

    if manifest is not None:
        validate_tool_manifest_against_function(func, manifest.parameters)

    if inspect.isbuiltin(func):
        # builtins are C-level and can't hold our node-type attribute; wrap them
        return _function_preserving_metadata(func)

    if not (
        asyncio.iscoroutinefunction(func)
        or inspect.isfunction(func)
        or inspect.ismethod(func)  # bound (and class) methods
        or isinstance(func, functools.partial)
    ):
        raise NodeCreationError(
            message=f"The provided function is not a valid coroutine or sync function it is {type(func)}.",
            notes=[
                "You must provide a valid function or coroutine function to make a node.",
            ],
        )

    return func


def _single_function_node(
    func: Callable[_P, Coroutine[None, None, _TOutput]] | Callable[_P, _TOutput],
    /,
    *,
    name: str | None = None,
    manifest: ToolManifest | None = None,
    middleware: Iterable[Middleware[_P, _TOutput]] | None = None,
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

    if isinstance(func, CallableSyncRTFunction) or isinstance(
        func, CallableAsyncRTFunction
    ):
        return func

    # `func` is an un-narrowed union here, so restate it; narrowed just below
    func = cast(
        "Callable[_P, Coroutine[None, None, _TOutput]] | Callable[_P, _TOutput]",
        _validate_and_normalize_callable(func, manifest),
    )

    unwrapped_func: Callable[_P, Coroutine[None, None, _TOutput]]
    is_sync = False
    if not asyncio.iscoroutinefunction(func):
        is_sync = True
        # narrowed: the guard above means `func` returns _TOutput, not a coroutine
        sync_func = cast(Callable[_P, _TOutput], func)

        async def wrapped_function(*args: _P.args, **kwargs: _P.kwargs) -> _TOutput:
            return await asyncio.to_thread(sync_func, *args, **kwargs)

        functools.update_wrapper(wrapped_function, func)
        unwrapped_func = wrapped_function
    else:
        unwrapped_func = func

    builder = FunctionNodeBuilder.function(
        unwrapped_func,
        name=name if name is not None else f"{unwrapped_func.__name__}",
        middleware=middleware,
        tool_details=manifest.description if manifest is not None else None,
        tool_params=manifest.parameters if manifest is not None else None,
    )

    completed_node_type = builder.build()

    if issubclass(completed_node_type, Node):
        if is_sync:
            new_func = cast(Callable[_P, _TOutput], func)
            return CallableSyncRTFunction(new_func, completed_node_type)
        else:
            new_func = cast(Callable[_P, Coroutine[None, None, _TOutput]], func)
            return CallableAsyncRTFunction(new_func, completed_node_type)

    raise NodeCreationError(
        message="The provided function did not create a valid node type.",
        notes=[
            "Please make a github issue with the details of what went wrong.",
        ],
    )


def function_node(
    func: Callable[_P, Coroutine[None, None, _TOutput]]
    | Callable[_P, _TOutput]
    | List[Callable[_P, Coroutine[None, None, _TOutput]] | Callable[_P, _TOutput]]
    | None = None,
    /,
    *,
    name: str | None = None,
    manifest: ToolManifest | None = None,
    middleware: Iterable[Middleware[_P, _TOutput]] | None = None,
) -> (
    CallableAsyncRTFunction[_P, _TOutput]
    | CallableSyncRTFunction[_P, _TOutput]
    | List[CallableAsyncRTFunction[_P, _TOutput] | CallableSyncRTFunction[_P, _TOutput]]
    | Callable[
        [Callable[_P, Coroutine[None, None, _TOutput]] | Callable[_P, _TOutput]],
        RTFunction[_P, _TOutput],
    ]
    | None
):
    """
    Creates a new Node type from a function that can be used in `rt.call()`.

    By default, it will parse the function's docstring and turn them into tool details and parameters. However, if
    you provide custom ToolManifest it will override that logic.

    Can be used three ways::

        # 1. direct call
        node = rt.function_node(my_fn, middleware=[guard])

        # 2. bare decorator
        @rt.function_node
        def my_fn(...): ...

        # 3. parametrized decorator (attach middleware / guardrails declaratively)
        @rt.function_node(middleware=[guard], name="echo")
        def my_fn(...): ...

    WARNING: If you overriding tool parameters. It is on you to make sure they will work with your function.

    NOTE: If you have already converted this function to a node this function will do nothing

    Args:
        func (Callable, optional): The function to convert into a Node. Omit it to use the
            parametrized-decorator form, which returns a decorator that takes the function.
        name (str, optional): Human-readable name for the node/tool.
        manifest (ToolManifest, optional): The details you would like to override the tool with.
        middleware (list[Middleware] | None): Middleware applied around the node boundary.
    """

    # No function yet -> parametrized-decorator form: bind the options and return
    # a decorator that finishes the job once the function is supplied.
    if func is None:

        def _decorator(
            f: Callable[_P, Coroutine[None, None, _TOutput]] | Callable[_P, _TOutput],
        ) -> (
            CallableAsyncRTFunction[_P, _TOutput] | CallableSyncRTFunction[_P, _TOutput]
        ):
            return function_node(f, name=name, manifest=manifest, middleware=middleware)

        return _decorator

    # handle the case where a list of functions is provided
    if isinstance(func, list):
        return [
            function_node(f, name=name, manifest=manifest, middleware=middleware)
            for f in func
        ]
    else:
        return _single_function_node(
            func, name=name, manifest=manifest, middleware=middleware
        )


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


def _partial_with_resolved_metadata(
    func: "functools.partial[_TOutput]",
) -> "functools.partial[_TOutput]":
    """Return a copy of a ``functools.partial`` with real name/qualname/doc.

    Sources ``__name__``/``__qualname__``/``__doc__`` from the wrapped callable
    (unwrapping nested partials) onto a fresh copy, leaving the caller's object
    untouched. The copy keeps the partial's reduced signature.

    Args:
        func: The ``functools.partial`` to normalise.

    Returns:
        A copy of ``func`` with metadata sourced from the underlying callable.
    """
    underlying: Callable = func
    while isinstance(underlying, functools.partial):
        underlying = underlying.func

    # discard the partial's boilerplate __doc__ in favour of the underlying one
    name = getattr(underlying, "__name__", "partial")
    qualname = getattr(underlying, "__qualname__", name)
    doc = getattr(underlying, "__doc__", None)

    resolved: "functools.partial[_TOutput]" = functools.partial(
        func.func, *func.args, **func.keywords
    )
    resolved.__name__ = name  # type: ignore[attr-defined]
    resolved.__qualname__ = qualname  # type: ignore[attr-defined]
    resolved.__doc__ = doc
    return resolved
