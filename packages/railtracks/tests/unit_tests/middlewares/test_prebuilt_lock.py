"""Unit tests for the prebuilt Lock middleware."""

import asyncio

from railtracks.prebuilt.middleware import Lock


async def test_serializes_concurrent_calls():
    active = 0
    peak = 0

    async def work(value):
        nonlocal active, peak
        active += 1
        peak = max(peak, active)
        await asyncio.sleep(0)
        active -= 1
        return value

    wrapped = Lock().wrap(work)

    assert await asyncio.gather(wrapped(1), wrapped(2)) == [1, 2]
    assert peak == 1
