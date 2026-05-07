from typing import TypeVar
from collections.abc import AsyncGenerator, AsyncIterable

_T = TypeVar("_T")

async def abatched(
    iterable: AsyncIterable[_T],
    n: int,
) -> AsyncGenerator[list[_T], None]:
    """Group an async iterable into fixed-size lists of up to ``n`` items."""
    batch: list[_T] = []
    async for item in iterable:
        batch.append(item)
        if len(batch) >= n:
            yield batch
            batch = []
    if batch:
        yield batch