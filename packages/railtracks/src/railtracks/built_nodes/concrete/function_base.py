from __future__ import annotations

from copy import deepcopy
from typing import (
    Generic,
    ParamSpec,
    Protocol,
    TypeVar,
    runtime_checkable,
)

from railtracks.nodes.nodes import Node

_TOutput = TypeVar("_TOutput")
_P = ParamSpec("_P")


@runtime_checkable
class RTFunction(Protocol, Generic[_P, _TOutput]):
    """
    A protocol for a function (callable) which contains an additional parameter called node_type which contains the node representation of this function.
    """

    node_type: type[Node[_P, _TOutput]]


    def extend_middleware(self, *middleware) -> RTFunction[_P, _TOutput]:
        """
        Returns a new Node type with the provided middleware attached. This does not modify the original node_type.
        """
        new_function_node = deepcopy(self)
        new_node_type = self.node_type.extend_middleware(*middleware)
        new_function_node.node_type = new_node_type
        
        return new_function_node
