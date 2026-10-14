import asyncio
import concurrent.futures
import random
import time

import pytest
import railtracks as rt


def slow_rng(timeout_len: float):
    time.sleep(timeout_len)
    return random.random()


SlowRNG = rt.function_node(slow_rng)


@pytest.mark.asyncio
async def test_async_runners_w_async():
    async def run_rng(timeout_len: float):
        conn = rt.Flow("test_async_runners_w_async", SlowRNG).connect()
        await conn.ainvoke(timeout_len)
        return conn.session.info

    contracts = [run_rng(0.2) for _ in range(5)]

    collected_data = await asyncio.gather(*contracts)

    for c in collected_data:
        assert isinstance(c.answer, float), "Expected a float result from RNGNode"
        assert len(c.node_forest.heap()) == 1


@pytest.mark.asyncio
async def test_async_runners_w_executor():
    with concurrent.futures.ThreadPoolExecutor() as executor:

        async def run_rng(timeout_len: float):
            conn = rt.Flow("test_async_runners_w_executor", SlowRNG).connect()
            await conn.ainvoke(timeout_len)
            return conn.session.info

        mapped_results = executor.map(lambda x: asyncio.run(run_rng(x)), [0.2] * 5)

        for m in mapped_results:
            assert isinstance(m.answer, float), "Expected a float result from RNGNode"


@pytest.mark.asyncio
async def nested_runner_call():
    return await rt.Flow("nested_runner_call", SlowRNG).ainvoke(0.2)


NestedRunner = rt.function_node(nested_runner_call)
