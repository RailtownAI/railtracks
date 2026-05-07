from __future__ import annotations

from collections.abc import AsyncGenerator, AsyncIterable
from typing import TypeVar

_T = TypeVar("_T")


async def abatched(
    source: AsyncIterable[_T], batch_size: int
) -> AsyncGenerator[list[_T], None]:
    """Collect items from an async iterable into fixed-size batches."""
    batch: list[_T] = []
    async for item in source:
        batch.append(item)
        if len(batch) >= batch_size:
            yield batch
            batch = []
    if batch:
        yield batch
