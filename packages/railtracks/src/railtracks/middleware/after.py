from typing import Awaitable, Callable, TypeVar

from railtracks.events.middleware import (
    MiddlewareOutputInvocationEvent,
    MiddlewareOutputResponseEvent,
)
from railtracks.events.send import emit, pipe
from railtracks.utils.unpack import unpack_async_sync

from .core import wrap_node

_R = TypeVar("_R")


def after_node(
    fn: Callable[[_R], Awaitable[_R]] | Callable[[_R], _R],
):
    """
    Special decorator to create a middleware that runs after the node completes. The wrapped function will run and then your after function will be called upon succesful completion of the function.

    NOTE: This middleware will not run the node raises an exception.
    """

    @wrap_node
    async def wrapper(call: Callable[..., Awaitable[_R]], *args, **kwargs):
        result = await call(*args, **kwargs)
        input_event = MiddlewareOutputInvocationEvent(
            response=result,
        )
        await emit(input_event)
        post_after_result = fn(result)

        result = await unpack_async_sync(post_after_result)

        output_event = MiddlewareOutputResponseEvent(
            response=result,
        )
        await emit(output_event)

        return result

    return wrapper
