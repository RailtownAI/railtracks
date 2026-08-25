from __future__ import annotations

from typing import (
    TYPE_CHECKING,
    ParamSpec,
    TypeVar,
)

if TYPE_CHECKING:
    from railtracks.built_nodes.function.base import (
        RTFunction,
    )
    from railtracks.nodes.nodes import Node


_P = ParamSpec("_P")
_TOutput = TypeVar("_TOutput")


def extract_node_from_function(
    func: RTFunction[_P, _TOutput],
) -> type[Node[_P, _TOutput]]:
    """
    Extracts the node type attached to a decorated function.

    Args:
        func: A callable decorated with ``@rt.function_node``.

    Returns:
        The node type built from ``func``.

    Raises:
        TypeError: If ``func`` is an undecorated callable, and so has no ``node_type``.
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
