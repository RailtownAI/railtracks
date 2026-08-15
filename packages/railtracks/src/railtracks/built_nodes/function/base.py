from __future__ import annotations

import functools
from typing import (
    Callable,
    Coroutine,
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
    ) -> RTFunction[_P, _TOutput]:
        """Returns a copy of this RTFunction with a different `node_type`. Does not modify this instance."""
        ...


class CallableSyncRTFunction(RTFunction[_P, _TOutput], Generic[_P, _TOutput]):
    def __init__(
        self, func: Callable[_P, _TOutput], node_type: type[Node[_P, _TOutput]]
    ):
        self.func = func
        self.node_type = node_type
        functools.update_wrapper(self, func, updated=())

    def __call__(self, *args: _P.args, **kwargs: _P.kwargs) -> _TOutput:
        return self.func(*args, **kwargs)

    def with_node_type(
        self, node_type: type[Node[_P, _TOutput]]
    ) -> CallableSyncRTFunction[_P, _TOutput]:
        """Returns a copy of this CallableSyncRTFunction with a different `node_type`. Does not modify this instance."""
        return CallableSyncRTFunction(self.func, node_type)


class CallableAsyncRTFunction(RTFunction[_P, _TOutput], Generic[_P, _TOutput]):
    def __init__(
        self,
        func: Callable[_P, Coroutine[None, None, _TOutput]],
        node_type: type[Node[_P, _TOutput]],
    ):
        self.func = func
        self.node_type = node_type
        functools.update_wrapper(self, func, updated=())

    async def __call__(self, *args: _P.args, **kwargs: _P.kwargs) -> _TOutput:
        return await self.func(*args, **kwargs)

    def with_node_type(
        self, node_type: type[Node[_P, _TOutput]]
    ) -> CallableAsyncRTFunction[_P, _TOutput]:
        """Returns a copy of this CallableAsyncRTFunction with a different `node_type`. Does not modify this instance."""
        return CallableAsyncRTFunction(self.func, node_type)
