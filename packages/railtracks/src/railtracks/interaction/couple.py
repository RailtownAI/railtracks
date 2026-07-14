from __future__ import annotations

from copy import deepcopy
from typing import ParamSpec, TypeVar, overload

from railtracks.built_nodes.concrete.function_base import RTFunction
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
    node: RTFunction[_P, _R], *middleware: Middleware[_P, _R]
) -> RTFunction[_P, _R]: ...


def couple(
    node: type[Node[_P, _R]] | RTFunction[_P, _R], *middleware: Middleware[_P, _R]
) -> type[Node[_P, _R]] | RTFunction[_P, _R]:
    """
    Attaches middleware to a Node. This function return a completely new Node type so it will not effect the original Node inputted.

    Args:
        node: The Node or RTFunction to attach middleware to.
        middleware: An iterable of Middleware instances to attach to the node.

    Ordering:
    - Middleware = [A, B, C] -> A wraps B, B wraps C, C wraps the node. A -> B -> C -> Node -> C -> B -> A
    - If there is previous middleware present these will wrap around them.
    """
    print(node)
    if isinstance(node, RTFunction):
        new_klass = deepcopy(node)
        new_node_type = node.node_type.extend_middleware(*middleware)
        new_klass.node_type = new_node_type

        return new_klass

    new_klass = node.extend_middleware(*middleware)

    return new_klass



def _deep_copy_rt_function(rt_function: RTFunction[_P, _R]) -> RTFunction[_P, _R]:
    
