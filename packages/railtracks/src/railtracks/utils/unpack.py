from typing import Awaitable, TypeVar

_T = TypeVar("_T")


async def unpack_async_sync(value: Awaitable[_T] | _T, /) -> _T:
    if isinstance(value, Awaitable):
        return await value
    else:
        return value
