from __future__ import annotations

from typing import TYPE_CHECKING, Iterable, ParamSpec, TypeVar, overload

from railtracks.built_nodes.middlewares.core import ModelMiddleware
from railtracks.middlewares.core import Middleware


from railtracks.built_nodes.concrete.function_base import RTFunction
from railtracks.nodes.nodes import Node


_P = ParamSpec("_P")
_R = TypeVar("_R")


@overload
def couple(
    node: type[Node[_P, _R]], middleware: Iterable[Middleware[_P, _R]]
) -> type[Node[_P, _R]]:
    ...

@overload
def couple(
    node: RTFunction[_P, _R], middleware: Iterable[Middleware[_P, _R]]
) -> RTFunction[_P, _R]:
    ...


def couple(
    node: type[Node[_P, _R]] | RTFunction[_P, _R], middleware: Iterable[Middleware[_P, _R]]
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
    new_klass = node.extend_middleware(*middleware)

    return new_klass
