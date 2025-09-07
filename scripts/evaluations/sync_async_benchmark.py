import asyncio
import time

import railtracks as rt


def sync_blocking(timeout: float):
    time.sleep(timeout)


Blocking = rt.function_node(sync_blocking)

lengths = [1, 2, 2, 2, 1]


async def top_level_sync_blocking():
    """
    A top-level function that blocks for a given timeout.
    """
    await rt.call_batch(Blocking, lengths)
    return None


TopLevel = rt.function_node(top_level_sync_blocking)


async def test_sync_blocking():
    """
    Test the sync blocking function.
    """
    start_time = time.time()
    await rt.call(TopLevel)
    end_time = time.time()
    print(f"Sync blocking task {lengths} took {end_time - start_time:.2f} seconds")


asyncio.run(test_sync_blocking())
