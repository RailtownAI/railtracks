from __future__ import annotations

from typing import ParamSpec, TypeVar, overload

from railtracks.built_nodes.concrete.function_base import RTFunction
from railtracks.built_nodes.easy_usage_wrappers.function import (
    CallableAsyncRTFunction,
    CallableSyncRTFunction,
)
from railtracks.middlewares.core import Middleware
from railtracks.nodes.nodes import Node

_P = ParamSpec("_P")
_R = TypeVar("_R")


@overload
def couple(
    node: type[Node[_P, _R]], *middleware: Middleware[_P, _R]
) -> type[Node[_P, _R]]: ...


@overload
def couple(
    node: CallableSyncRTFunction[_P, _R], *middleware: Middleware[_P, _R]
) -> CallableSyncRTFunction[_P, _R]: ...


@overload
def couple(
    node: CallableAsyncRTFunction[_P, _R], *middleware: Middleware[_P, _R]
) -> CallableAsyncRTFunction[_P, _R]: ...


def couple(
    node: type[Node[_P, _R]] | RTFunction[_P, _R], *middleware: Middleware[_P, _R]
) -> type[Node[_P, _R]] | RTFunction[_P, _R]:
    """
    Attaches middleware to a Node or RTFunction. Returns a new object; the one passed in is never modified.

    Args:
        node: The Node or RTFunction to attach middleware to.
        middleware: Middleware instances to attach to the node.

    Ordering:
    - Middleware = [A, B, C] -> A wraps B, B wraps C, C wraps the node. A -> B -> C -> Node -> C -> B -> A
    - Existing middleware on `node` is preserved and wraps around the newly added middleware
      (the new middleware ends up innermost, closest to the node).
    """
    if isinstance(node, RTFunction):
        new_node_type = node.node_type.extend_middleware(*middleware)
        return node.with_node_type(new_node_type)

    new_klass = node.extend_middleware(*middleware)

    return new_klass
