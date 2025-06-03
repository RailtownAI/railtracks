import asyncio
import warnings

from typing import ParamSpec, Callable, TypeVar

from ..run import get_runner, Runner
from ..context import parent_id
from ..nodes.nodes import Node

_TOutput = TypeVar("_TOutput")
_P = ParamSpec("_P")


async def call(node: Callable[_P, Node[_TOutput]], *args: _P.args, **kwargs: _P.kwargs):
    """
    Call a node from within a node inside the framework. This will return a coroutine that you can interact with
    in whatever way using the `asyncio` framework.

    Args:
        node: The node type you would like to create
        *args: The arguments to pass to the node
        **kwargs: The keyword arguments to pass to the node


    """
    # there are 4 cases that we need to handle in this function.
    # 1. The runner exists and the parent node id is set
    #  - in this case we can just call the node and return the result.
    # 2. The runner exists and the parent node id is not set
    #  - This is the case where this is actually the first node is called, however this is no different from case 1
    # 3. The runner does not exist and the parent node id is set.
    #  - This makes no sense and means a system invariant has been broken.
    # 4. The runner does not exist and the parent node id is not set.
    #  - In this case we have to start the system from scratch and create a new runner.

    runner: Runner = get_runner()
    if runner is None:
        # in the case that a runner doesn't exists we will need to wrap it.
        # we will use the default values in the system (see config.py)
        with Runner():
            return await call(node, *args, **kwargs)

    # the reference to current node running must be collected and passed into the state object
    p_n_id = parent_id.get()
    # but we also must update the variable so if the child node makes its own calls it is operating on the correct ID.

    try:
        # note the call function should be able to handle when the parent node id is none.
        return await runner.call(p_n_id, node, *args, **kwargs)
    except (asyncio.TimeoutError, asyncio.CancelledError):
        child_id = parent_id.get()
        if child_id == p_n_id:
            warnings.warn(
                "The child node was not created before the call was cancelled."
            )
            return

        await runner.cancel(child_id)
    finally:
        # reset the parent id to the original value
        parent_id.set(p_n_id)


# TODO add support for any general user defined streaming object
def stream(item: str):
    runner: Runner = get_runner()
    if runner is None:
        raise RuntimeError("You cannot stream if there is no runner set.")
    return runner.stream(item)
