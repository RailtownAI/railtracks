"""Unit tests for the prebuilt Lock middleware."""

import asyncio

from railtracks.prebuilt.middleware import Lock


async def _peak_concurrency(lock: Lock) -> int:
    active = 0
    peak = 0

    async def work(value):
        nonlocal active, peak
        active += 1
        peak = max(peak, active)
        await asyncio.sleep(0)
        active -= 1
        return value

    wrapped = lock.wrap(work)

    assert await asyncio.gather(wrapped(1), wrapped(2)) == [1, 2]
    return peak


async def test_serializes_concurrent_calls():
    assert await _peak_concurrency(Lock()) == 1


def test_serializes_concurrent_calls_on_every_event_loop():
    # each sync flow.invoke() runs on a fresh loop, as asyncio.run does
    lock = Lock()

    assert asyncio.run(_peak_concurrency(lock)) == 1
    assert asyncio.run(_peak_concurrency(lock)) == 1
