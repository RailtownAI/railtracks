from __future__ import annotations

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
