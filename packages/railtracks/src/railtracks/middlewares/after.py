import inspect
from typing import Awaitable, Callable, TypeVar

from railtracks.utils.unpack import unpack_async_sync
from .core import middleware

_R = TypeVar("_R")

def after(
    fn: Callable[[_R], Awaitable[_R]] | Callable[[_R], _R],
):
    """
    Special decorator to create a middleware that runs after the node completes. The wrapped function will run and then your after function will be called upon succesful completion of the function.

    NOTE: This middleware will not run the node raises an exception.
    """

    @middleware
    async def wrapper(call: Callable[..., Awaitable[_R]], *args, **kwargs):
        result = await call(*args, **kwargs)
        post_after_result = fn(result)

        return await unpack_async_sync(post_after_result)

    return wrapper