from __future__ import annotations

from typing import (
    TYPE_CHECKING,
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
    func: RTAsyncFunction[_P, _TOutput],
) -> Type[Node[AsyncDynamicFunctionNode[_P, _TOutput]]]:
    pass


@overload
def extract_node_from_function(
    func: RTSyncFunction[_P, _TOutput],
) -> Type[Node[SyncDynamicFunctionNode[_P, _TOutput]]]:
    pass


def extract_node_from_function(
    func: RTFunction[_P, _TOutput],
):
    """
    Extracts the node type from a function or a callable.
    """
    # we enter this block if the user passed in a previously from function decorated node.
    if hasattr(func, "node_type"):
        node = func.node_type

    # if the node is a pure function we just raise a type error
    else:
        raise TypeError(
            f"expected RTFunction types, got type {type(func)}. "
            "Please decorate your function with @rt.function_node."
        )

    return node
