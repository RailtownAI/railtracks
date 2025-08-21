from typing import Callable, Coroutine, ParamSpec, Type, TypeVar, overload

from railtracks.node import Node

from .concrete import (
    AsyncDynamicFunctionNode,
    RTAsyncFunction,
    RTFunction,
    RTSyncFunction,
    SyncDynamicFunctionNode,
)

_P = ParamSpec("_P")
_TOutput = TypeVar("_TOutput")


@overload
def extract_node_from_function(
    func: Callable[_P, Coroutine[None, None, _TOutput]] | RTAsyncFunction[_P, _TOutput],
) -> Type[Node[AsyncDynamicFunctionNode[_P, _TOutput]]]:
    pass


@overload
def extract_node_from_function(
    func: Callable[_P, _TOutput] | RTSyncFunction[_P, _TOutput],
) -> Type[Node[SyncDynamicFunctionNode[_P, _TOutput]]]:
    pass


def extract_node_from_function(
    func: Callable[_P, Coroutine[None, None, _TOutput] | _TOutput]
    | RTFunction[_P, _TOutput],
):
    """
    Extracts the node type from a function or a callable.
    Full implementation with concrete types.
    """
    # we enter this block if the user passed in a previously from function decorated node.
    if hasattr(func, "node_type"):
        node = func.node_type

    # if the node is a pure function then we will also convert it to a node.
    else:
        # Import function_node from easy_usage_wrappers within builtnodes
        from .easy_usage_wrappers import function_node

        node = function_node(func).node_type

    return node