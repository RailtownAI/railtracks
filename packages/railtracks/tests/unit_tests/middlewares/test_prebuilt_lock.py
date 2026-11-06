"""Unit tests for the prebuilt Lock middleware."""

import asyncio
import gc
import weakref

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


def test_does_not_keep_closed_loops_alive():
    lock = Lock()

    async def run_and_ref_loop():
        await _peak_concurrency(lock)
        return weakref.ref(asyncio.get_running_loop())

    # a lock that had to wait holds a strong reference to its loop
    first_loop = asyncio.run(run_and_ref_loop())
    asyncio.run(_peak_concurrency(lock))
    gc.collect()

    assert first_loop() is None
