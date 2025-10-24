from __future__ import annotations

import asyncio
from types import FunctionType
from typing import (
    TYPE_CHECKING,
    Callable,
    Coroutine,
    ParamSpec,
    TypeVar,
    overload,
)
from uuid import uuid4

from railtracks.context.central import (
    activate_publisher,
    get_local_config,
    get_parent_id,
    get_publisher,
    get_run_id,
    is_context_active,
    is_context_present,
    shutdown_publisher,
)
from railtracks.exceptions import GlobalTimeOutError
from railtracks.nodes.utils import extract_node_from_function
from railtracks.pubsub.messages import (
    FatalFailure,
    RequestCompletionMessage,
    RequestCreation,
    RequestFinishedBase,
)
from railtracks.pubsub.utils import output_mapping

if TYPE_CHECKING:
    from railtracks.built_nodes.concrete import RTFunction
    from railtracks.nodes.nodes import Node

_P = ParamSpec("_P")
_TOutput = TypeVar("_TOutput")


@overload
async def call(
    node_: RTFunction[_P, _TOutput],
    *args: _P.args,
    **kwargs: _P.kwargs,
) -> _TOutput: ...


@overload
async def call(
    node_: Callable[_P, Node[_TOutput]],
    *args: _P.args,
    **kwargs: _P.kwargs,
) -> _TOutput: ...


async def call(
    node_: Callable[_P, Node[_TOutput]] | RTFunction[_P, _TOutput],
    *args: _P.args,
    **kwargs: _P.kwargs,
) -> _TOutput:
    """
    Call a node from within a node inside the framework. This will return a coroutine that you can interact with
    in whatever way using async/await logic.

    Usage:
    ```python
    # for sequential operation
    result = await call(NodeA, "hello world", 42)

    # for parallel operation
    tasks = [call(NodeA, "hello world", i) for i in range(10)]
    results = await asyncio.gather(*tasks)
    ```

    Args:
        node: The node type you would like to create. This could be a function decorated with `@function_node`, a function, or a Node instance.
        *args: The arguments to pass to the node
        **kwargs: The keyword arguments to pass to the node
    """
    node: Callable[_P, Node[_TOutput]]
    # this entire section is a bit of a typing nightmare becuase all overloads we provide.
    if isinstance(node_, FunctionType):
        node = extract_node_from_function(node_)
    else:
        node = node_

    # if the context is none then we will need to create a wrapper for the state object to work with.
    if not is_context_present():
        # we have to use lazy import here to prevent a circular import issue. This is a must have unfortunately.
        from railtracks import Session

        with Session():
            result = await _start(node, args=args, kwargs=kwargs)
            return result

    # if the context is not active then we know this is the top level request
    if not is_context_active():
        result = await _start(node, args=args, kwargs=kwargs)
        return result

    # if the context is active then we can just run the node
    result = await _run(node, args=args, kwargs=kwargs)
    return result


def _regular_message_filter(request_id: str):
    """
    Returns a filter function that checks if the message matches the request ID.
    """

    def filter_func(item: RequestCompletionMessage) -> bool:
        if isinstance(item, RequestFinishedBase):
            return item.request_id == request_id
        return False

    return filter_func


def _top_level_message_filter(request_id: str):
    """
    Returns a filter function that checks if the message matches the request ID.
    """

    def message_filter(item: RequestCompletionMessage) -> bool:
        # we want to filter and collect the message that matches this request_id
        matches_request_id = (
            isinstance(item, RequestFinishedBase) and item.request_id == request_id
        )
        fatal_failure = isinstance(item, FatalFailure)

        return matches_request_id or fatal_failure

    return message_filter


async def _start(
    node: Callable[_P, Node[_TOutput]],
    args,
    kwargs,
):
    await activate_publisher()

    # there is a really funny edge case that we need to handle here to prevent if the user itself throws an timeout
    #  exception. It should be handled differently then the global timeout exception.
    #  Yes I am aware that is a bit of a hack but this is the best way to handle this specific case.
    timeout_exception_flag = {"value": False}

    async def wrapped_fut(f: Coroutine):
        try:
            return await f
        except asyncio.TimeoutError as error:
            timeout_exception_flag["value"] = True
            raise error

    timeout = get_local_config().timeout
    fut = _execute(
        node, args=args, kwargs=kwargs, message_filter=_top_level_message_filter
    )
    # Here we wait the completion of the future with timeouts.
    try:
        result = await asyncio.wait_for(wrapped_fut(fut), timeout=timeout)
    except asyncio.TimeoutError as e:
        # if the internal flag is set then the coroutine itself raised a timeout error and it was not the wait
        #  for function.
        if timeout_exception_flag["value"]:
            raise e

        raise GlobalTimeOutError(timeout=timeout)
    finally:
        await shutdown_publisher()

    return result


async def _run(
    node: Callable[_P, Node[_TOutput]],
    args,
    kwargs,
):
    """
    Executes the given Node set up using the provided arguments and keyword arguments.
    """
    return await _execute(
        node, args=args, kwargs=kwargs, message_filter=_regular_message_filter
    )


async def _execute(
    node: Callable[_P, Node[_TOutput]],
    args,
    kwargs,
    message_filter: Callable[[str], Callable[[RequestCompletionMessage], bool]],
) -> _TOutput:
    publisher = get_publisher()

    # generate a unique request ID for this request. We need to hold this reference here because we will use it to
    # filter for its completion
    request_id = str(uuid4())

    # note we set the listener before we publish the messages ensure that we do not miss any messages
    # I am actually a bit worried about this logic and I think there is a chance of a bug popping up here.
    f = publisher.listener(message_filter(request_id), output_mapping)

    await publisher.publish(
        RequestCreation(
            current_node_id=get_parent_id(),
            current_run_id=get_run_id(),
            new_request_id=request_id,
            running_mode="async",
            new_node_type=node,
            args=args,
            kwargs=kwargs,
        )
    )

    return await f
