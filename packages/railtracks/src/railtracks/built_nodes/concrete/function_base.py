from __future__ import annotations

import functools
from typing import (
    Callable,
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

    def with_node_type(
        self, node_type: type[Node[_P, _TOutput]]
    ) -> "RTFunction[_P, _TOutput]":
        """Returns a copy of this RTFunction with a different `node_type`. Does not modify this instance."""
        ...


