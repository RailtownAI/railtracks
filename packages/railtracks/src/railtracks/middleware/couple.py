from typing import ParamSpec, TypeVar, overload

from railtracks.built_nodes.concrete.function_base import RTFunction
from railtracks.middleware.primitives import Wrapper
from railtracks.nodes.nodes import Node
    


_P = ParamSpec("_P")
_R = TypeVar("_R")

@overload
def couple(
    node: type[Node[_P, _R]], *couplers: Wrapper[_P, _R]
) -> type[Node[_P, _R]]:
    ...

@overload
def couple(
    node: RTFunction[_P, _R], *couplers: Wrapper[_P, _R]
) -> RTFunction[_P, _R]:
    ...

def couple(node: type[Node[_P, _R]] | RTFunction[_P, _R], *couplers: Wrapper[_P, _R]) -> type[Node[_P, _R]] | RTFunction[_P, _R]:
    unwrapped_node: type[Node[_P, _R]]
    is_rt_function: bool
    if isinstance(node, RTFunction):
        unwrapped_node = node.node_type
        is_rt_function = True
    else:
        unwrapped_node = node
        is_rt_function = False

    new_klass = unwrapped_node.extend_middleware(*couplers) 

    if is_rt_function:
        node.node_type = new_klass
        return node
    else:
        return new_klass