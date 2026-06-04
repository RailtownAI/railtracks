from __future__ import annotations

from typing import (
    TYPE_CHECKING,
    ParamSpec,
    TypeVar,
)

if TYPE_CHECKING:
    from railtracks.built_nodes.concrete import (
        RTFunction,
    )


_P = ParamSpec("_P")
_TOutput = TypeVar("_TOutput")


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
