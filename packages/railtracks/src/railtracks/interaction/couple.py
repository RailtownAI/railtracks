from __future__ import annotations

from typing import TYPE_CHECKING, Iterable, ParamSpec, TypeVar, overload

from railtracks.built_nodes.llm.middleware.core import ModelMiddleware

if TYPE_CHECKING:
    from railtracks.built_nodes.function.base import (
        CallableAsyncRTFunction,
        CallableSyncRTFunction,
        RTFunction,
    )
    from railtracks.middleware.core import Middleware
    from railtracks.nodes.nodes import Node


_P = ParamSpec("_P")
_R = TypeVar("_R")


@overload
def couple(
    node: type[Node[_P, _R]],
    *,
    middleware: Iterable[Middleware[_P, _R]],
    model_middleware: Iterable[ModelMiddleware],
) -> type[Node[_P, _R]]: ...


@overload
def couple(
    node: type[Node[_P, _R]],
    *,
    middleware: Iterable[Middleware[_P, _R]] | None = None,
    model_middleware: Iterable[ModelMiddleware],
) -> type[Node[_P, _R]]: ...


@overload
def couple(
    node: type[Node[_P, _R]],
    *,
    middleware: Iterable[Middleware[_P, _R]],
    model_middleware: Iterable[ModelMiddleware] | None = None,
) -> type[Node[_P, _R]]: ...


@overload
def couple(
    node: CallableSyncRTFunction[_P, _R], *, middleware: Iterable[Middleware[_P, _R]]
) -> CallableSyncRTFunction[_P, _R]: ...


@overload
def couple(
    node: CallableAsyncRTFunction[_P, _R], *, middleware: Iterable[Middleware[_P, _R]]
) -> CallableAsyncRTFunction[_P, _R]: ...


def couple(
    node: type[Node[_P, _R]] | RTFunction[_P, _R],
    *,
    middleware: Iterable[Middleware[_P, _R]] | None = None,
    model_middleware: Iterable[ModelMiddleware] | None = None,
) -> type[Node[_P, _R]] | RTFunction[_P, _R]:
    """
    Attaches middleware to a Node or RTFunction. Returns a new deepcopied Node or RTFunction; the one passed in is never modified.

    Args:
        node: The Node or RTFunction to attach middleware to.
        middleware: Middleware instances to attach to the node.
        model_middleware: ModelMiddleware instances to attach to the node.

    Ordering:
    - Middleware = [A, B, C] -> A wraps B, B wraps C, C wraps the node. A -> B -> C -> Node -> C -> B -> A
    - Existing middleware on `node` is preserved and wraps around the newly added middleware
      (the new middleware ends up innermost, closest to the node).
    """
    from railtracks.built_nodes.function.base import RTFunction

    if middleware is None and model_middleware is None:
        return node

    if isinstance(node, RTFunction):
        if model_middleware is not None:
            raise ValueError("Your function node does not have a model to wrap")
        if middleware:
            new_node_type = node.node_type.extend_middleware(*middleware)
        else:
            return node

        return node.with_node_type(new_node_type)

    new_klass = node

    if middleware:
        new_klass = new_klass.extend_middleware(*middleware)
    if model_middleware:
        new_klass = new_klass.extend_model_middleware(*model_middleware)

    return new_klass
