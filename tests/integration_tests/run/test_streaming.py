import random
import time
import asyncio

import requestcompletion as rc


from requestcompletion import ExecutorConfig


async def streaming_rng():
    number = random.random()
    await rc.stream(str(number))

    return number


StreamingRNGNode = rc.library.from_function(streaming_rng)


def test_simple_streamer():
    class SubObject:
        def __init__(self):
            self.finished_message = None

        def handle(self, item: str):
            self.finished_message = item

    sub = SubObject()
    with rc.Runner(
        executor_config=rc.ExecutorConfig(
            logging_setting="NONE", subscriber=sub.handle
        ),
    ) as runner:
        finished_result = runner.run_sync(StreamingRNGNode)

    # force close streams flag must be set to false to allow the slow streaming to finish.

    assert isinstance(finished_result.answer, float)
    assert sub.finished_message == str(finished_result.answer)

    assert 0 < finished_result.answer < 1


# rather annoyingly this test could fail but it should be good nearly all of the time
def test_slow_streamer():
    class Sub:
        def __init__(self):
            self.finished_message = None

        def handle(self, item: str) -> None:
            # make this really slow so it is likely to not finish by the time execution is complete
            time.sleep(1)
            self.finished_message = item

    sub = Sub()
    with rc.Runner(executor_config=ExecutorConfig(subscriber=sub.handle)) as runner:
        finished_result = runner.run_sync(StreamingRNGNode)

    assert isinstance(finished_result.answer, float)
    assert sub.finished_message is not None


async def rng_tree_streamer(num_calls: int, parallel_call_nums: int, multiplier: int):
    data = []
    for _ in range(num_calls):
        contracts = [rc.call(StreamingRNGNode) for _ in range(parallel_call_nums)]
        responses = await asyncio.gather(*contracts)
        responses = [r * multiplier for r in responses]
        for r in responses:
            await rc.stream(str(r))

        data.extend(responses)

    return data


RNGTreeStreamer = rc.library.from_function(rng_tree_streamer)


def rng_stream_tester(
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
    with rc.Runner(
        executor_config=ExecutorConfig(logging_setting="NONE", subscriber=sub.handle)
    ) as run:
        finished_result = run.run_sync(
            RNGTreeStreamer, num_calls, parallel_call_nums, multiplier
        )

    assert isinstance(finished_result.answer, list)
    assert len(finished_result.answer) == num_calls * parallel_call_nums

    assert all([0 < x < 1 * multiplier for x in finished_result.answer])

    assert len(sub.total_streams) == num_calls * parallel_call_nums * 2
    assert set(sub.total_streams) == set([str(x) for x in finished_result.answer])


def test_rng_streamer():
    rng_stream_tester(3, 3)


def test_rng_streamer_2():
    rng_stream_tester(1, 15)


def test_rng_streamer_chaos():
    rng_stream_tester(4, 25)


def test_rng_streamer_chaos_2():
    rng_stream_tester(2, 15)
