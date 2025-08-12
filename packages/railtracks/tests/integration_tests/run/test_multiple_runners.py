import asyncio
import concurrent.futures
import railtracks as rt
import pytest


import time
import random


def slow_rng(timeout_len: float):
    time.sleep(timeout_len)
    return random.random()


SlowRNG = rt.function_node(slow_rng)


def test_sync_runners_w_executor():
    with concurrent.futures.ThreadPoolExecutor() as executor:

        def run_rng(timeout_len: float):
            with rt.Session(logging_setting="NONE") as run:
                return rt.call_sync(SlowRNG, timeout_len)

        mapped_results = executor.map(run_rng, [0.2] * 5)

        for m in mapped_results:
            assert isinstance(m, float), "Expected a float result from RNGNode"


@pytest.mark.asyncio
async def test_async_runners_w_async():
    async def run_rng(timeout_len: float):
        with rt.Session(logging_setting="NONE") as run:
            await rt.call(SlowRNG, timeout_len)
            return run.info

    contracts = [run_rng(0.2) for _ in range(5)]

    collected_data = await asyncio.gather(*contracts)

    for c in collected_data:
        assert isinstance(c.answer, float), "Expected a float result from RNGNode"
        assert len(c.node_forest.heap()) == 1


@pytest.mark.asyncio
async def test_async_runners_w_executor():
    with concurrent.futures.ThreadPoolExecutor() as executor:

        async def run_rng(timeout_len: float):
            with rt.Session(logging_setting="NONE") as run:
                result = await rt.call(SlowRNG, timeout_len)
                return run.info

        mapped_results = executor.map(lambda x: asyncio.run(run_rng(x)), [0.2] * 5)

        for m in mapped_results:
            assert isinstance(m.answer, float), "Expected a float result from RNGNode"


def nested_runner_call():
    with rt.Session(logging_setting="NONE") as run:
        result = rt.call_sync(SlowRNG, 0.2)
        return result


NestedRunner = rt.function_node(nested_runner_call)
