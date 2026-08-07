import functools
from typing import Awaitable, Callable, TypeVar, overload

from railtracks.utils.unpack import unpack_async_sync

from .core import Middleware, wrap_node

_R = TypeVar("_R")


@overload
def after_node(
    fn: Callable[[_R], Awaitable[_R]], /, *, name: str | None = None
) -> Middleware[..., _R]: ...


@overload
def after_node(
    *, name: str | None = None
) -> Callable[
    [Callable[[_R], Awaitable[_R]] | Callable[[_R], _R]], Middleware[..., _R]
]: ...


def after_node(
    fn: Callable[[_R], Awaitable[_R]] | Callable[[_R], _R] | None = None,
    /,
    *,
    name: str | None = None,
) -> (
    Middleware[..., _R]
    | Callable[
        [Callable[[_R], Awaitable[_R]] | Callable[[_R], _R]], Middleware[..., _R]
    ]
):
    """
    Special decorator to create a middleware that runs after the node completes. The wrapped function will run and then your after function will be called upon succesful completion of the function.

    NOTE: This middleware will not run the node raises an exception.
    """

    if fn is None:
        return lambda f: wrap_node(_wrapper(f), name=name)

    return wrap_node(_wrapper(fn), name=name)


def _wrapper(func: Callable[[_R], Awaitable[_R]] | Callable[[_R], _R], /):
    @functools.wraps(func)
    async def wrapper(call: Callable[..., Awaitable[_R]], *args, **kwargs):
        result = await call(*args, **kwargs)
        post_after_result = func(result)

        return await unpack_async_sync(post_after_result)

    return wrapper
