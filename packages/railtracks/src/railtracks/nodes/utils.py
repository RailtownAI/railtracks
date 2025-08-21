from __future__ import annotations

from typing import (
    TYPE_CHECKING,
    Callable,
    Coroutine,
    ParamSpec,
    Type,
    TypeVar,
    overload,
)

if TYPE_CHECKING:
    from railtracks.built_nodes.concrete import (
        AsyncDynamicFunctionNode,
        RTAsyncFunction,
        RTFunction,
        RTSyncFunction,
        SyncDynamicFunctionNode,
    )

from railtracks.nodes.nodes import Node

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
    """
    # we enter this block if the user passed in a previously from function decorated node.
    if hasattr(func, "node_type"):
        node = func.node_type

    # if the node is a pure function then we will also convert it to a node.
    else:
        # since this task is completed at run_time we will use a lazy import here.
        from railtracks import (
            function_node,
        )

        node = function_node(func).node_type
    # If a function is passed, we will convert it to a node
    # we have to use lazy import here to prevent a circular import issue. Bad design I know :(

    return node
