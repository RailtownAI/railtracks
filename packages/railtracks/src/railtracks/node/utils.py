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
    from .nodes import Node

_P = ParamSpec("_P")
_TOutput = TypeVar("_TOutput")


@overload
def extract_node_from_function(
    func: Callable[_P, Coroutine[None, None, _TOutput]],
) -> Type["Node"]:
    pass


@overload
def extract_node_from_function(
    func: Callable[_P, _TOutput],
) -> Type["Node"]:
    pass


def extract_node_from_function(
    func: Callable[_P, Coroutine[None, None, _TOutput] | _TOutput],
):
    """
    Extracts the node type from a function or a callable.
    
    Note: This is the basic version without circular dependencies.
    The full implementation with concrete types is in builtnodes module.
    """
    # Check if the function already has a node type attached
    if hasattr(func, "node_type"):
        return func.node_type
    
    # This will be handled by the builtnodes module
    # For now, just return the function - the higher level modules will handle conversion
    return func