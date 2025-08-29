from __future__ import annotations

import asyncio
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    Iterable,
    ParamSpec,
    TypeVar,
)

if TYPE_CHECKING:
    from railtracks.built_nodes.easy_usage_wrappers import (
        _AsyncNodeAttachedFunc,
        _SyncNodeAttachedFunc,
    )
from railtracks.nodes.nodes import Node

from ._call import call

_P = ParamSpec("_P")
_TOutput = TypeVar("_TOutput")


async def call_batch(
    node: Callable[..., Node[_TOutput]]
    | Callable[..., _TOutput]
    | _AsyncNodeAttachedFunc[_P, _TOutput]
    | _SyncNodeAttachedFunc[_P, _TOutput],
    *iterables: Iterable[Any],
    return_exceptions: bool = True,
):
    """
    Complete a node over multiple iterables, allowing for parallel execution.

    Note the results will be returned in the order of the iterables, not the order of completion.

    If one of the nodes returns an exception, the thrown exception will be included as a response.

    Args:
        node: The node type to create.
        *iterables: The iterables to map the node over.
        return_exceptions: If True, exceptions will be returned as part of the results.
            If False, exceptions will be raised immediately, and you will lose access to the results.
            Defaults to true.

    Returns:
        An iterable of results from the node.

    Usage:
        ```python
        results = await batch(NodeA, ["hello world"] * 10)
        for result in results:
            handle(result)
        ```
    """
    # this is big typing disaster but there is no way around it. Try if if you want to.
    contracts = [call(node, *args) for args in zip(*iterables)]

    results = await asyncio.gather(*contracts, return_exceptions=return_exceptions)
    return results
