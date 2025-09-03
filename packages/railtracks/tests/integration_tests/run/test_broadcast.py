import asyncio
import random
import time
import pytest
import railtracks as rt


async def streaming_rng():
    number = random.random()
    await rt.broadcast(str(number))

    return number


StreamingRNGNode = rt.function_node(streaming_rng)


async def test_simple_streamer():
    class SubObject:
        def __init__(self):
            self.finished_message = None

        def handle(self, item: str):
            self.finished_message = item

    sub = SubObject()
    with rt.Session(
        logging_setting="NONE",
        broadcast_callback=sub.handle,
    ):
        finished_result = await rt.call(StreamingRNGNode)

    # force close streams flag must be set to false to allow the slow streaming to finish.

    assert isinstance(finished_result, float)
    assert sub.finished_message == str(finished_result)

    assert 0 < finished_result < 1


# rather annoyingly this test could fail but it should be good nearly all of the time
async def test_slow_streamer():
    class Sub:
        def __init__(self):
            self.finished_message = None

        def handle(self, item: str) -> None:
            # make this really slow so it is likely to not finish by the time execution is complete
            time.sleep(1)
            self.finished_message = item

    sub = Sub()
    with rt.Session(broadcast_callback=sub.handle):
        finished_result = await rt.call(StreamingRNGNode)

    assert isinstance(finished_result, float)
    assert sub.finished_message is not None


async def rng_tree_streamer(num_calls: int, parallel_call_nums: int, multiplier: int):
    data = []
    for _ in range(num_calls):
        contracts = [rt.call(StreamingRNGNode) for _ in range(parallel_call_nums)]
        responses = await asyncio.gather(*contracts)
        responses = [r * multiplier for r in responses]
        for r in responses:
            await rt.broadcast(str(r))

        data.extend(responses)

    return data


RNGTreeStreamer = rt.function_node(rng_tree_streamer)


async def rng_stream_tester(
    num_calls=3,
    parallel_call_nums=3,
    multiplier=1,
):
    class Sub:
        def __init__(self):
            self.total_streams = []
            self.asyncio_lock = asyncio.Lock()

        async def handle(self, item: str) -> None:
            async with self.asyncio_lock:
                self.total_streams.append(item)

    sub = Sub()
    with rt.Session(logging_setting="NONE", broadcast_callback=sub.handle):
        finished_result = await rt.call(
            RNGTreeStreamer, num_calls, parallel_call_nums, multiplier
        )

    assert isinstance(finished_result, list)
    assert len(finished_result) == num_calls * parallel_call_nums

    assert all(0 < x < 1 * multiplier for x in finished_result)

    assert len(sub.total_streams) == num_calls * parallel_call_nums * 2
    assert set(sub.total_streams) == {str(x) for x in finished_result}

@pytest.mark.asyncio
async def test_rng_streamer():
    await rng_stream_tester(3, 3)

@pytest.mark.asyncio
async def test_rng_streamer_2():
    await rng_stream_tester(1, 15)

@pytest.mark.asyncio
async def test_rng_streamer_chaos():
    await rng_stream_tester(4, 25)

@pytest.mark.asyncio
async def test_rng_streamer_chaos_2():
    await rng_stream_tester(2, 15)
