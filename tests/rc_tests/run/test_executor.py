from __future__ import annotations

import asyncio
import random
from typing import List

import pytest
import requestcompletion as rc
from requestcompletion.exceptions import GlobalTimeOutError, NodeInvocationError
from typing_extensions import Self


RNGNode = rc.library.from_function(random.random)


async def many_calls(num_calls: int, parallel_calls: int):
    data = []
    for _ in range(num_calls):
        contracts = [rc.call(RNGNode) for _ in range(parallel_calls)]
        results = await asyncio.gather(*contracts)
        data.extend(results)
    return data


ManyCalls = rc.library.from_function(many_calls)


def many_calls_tester(num_calls: int, parallel_calls: int):
    with rc.Runner(executor_config=rc.ExecutorConfig(logging_setting="NONE")) as run:
        finished_result = run.run_sync(ManyCalls, num_calls, parallel_calls)

    ans = finished_result.answer

    assert isinstance(ans, list)
    assert len(ans) == num_calls * parallel_calls
    assert all([0 < x < 1 for x in ans])
    assert {x.step for x in finished_result.all_stamps} == {
        i for i in range(num_calls * parallel_calls * 2 + 2)
    }

    assert len(finished_result.all_stamps) == 2 * num_calls * parallel_calls + 2


@pytest.mark.timeout(5)
def test_no_deadlock():
    num_calls = 4
    parallel_calls = 55

    many_calls_tester(num_calls, parallel_calls)


def test_small_no_deadlock():
    num_calls = 10
    parallel_calls = 15

    many_calls_tester(num_calls, parallel_calls)


def test_large_no_deadlock():
    num_calls = 45
    parallel_calls = 23

    many_calls_tester(num_calls, parallel_calls)


def test_simple_rng():
    with rc.Runner(executor_config=rc.ExecutorConfig(logging_setting="NONE")) as run:
        result = run.run_sync(RNGNode)

    assert 0 < result.answer < 1


class NestedManyCalls(rc.Node):
    def __init__(self, num_calls: int, parallel_calls: int, depth: int):
        self.num_calls = num_calls
        self.parallel_calls = parallel_calls
        self.depth = depth
        super().__init__()

    async def invoke(
        self,
    ):
        data = []
        for _ in range(self.num_calls):
            if self.depth == 0:
                contracts = [rc.call(RNGNode) for _ in range(self.parallel_calls)]
                results = await asyncio.gather(*contracts)

            else:
                contracts = [
                    rc.call(
                        NestedManyCalls,
                        self.num_calls,
                        self.parallel_calls,
                        self.depth - 1,
                    )
                    for _ in range(self.parallel_calls)
                ]

                results = await asyncio.gather(*contracts)
                # flatten the list here.
                results = [x for y in results for x in y]
            data.extend(results)
        return data

    @classmethod
    def pretty_name(cls) -> str:
        return "NestedManyCalls"


def nested_many_calls_tester(num_calls: int, parallel_calls: int, depth: int):
    with rc.Runner(executor_config=rc.ExecutorConfig(logging_setting="NONE")) as run:
        finished_result = run.run_sync(
            NestedManyCalls, num_calls, parallel_calls, depth
        )

    ans = finished_result.answer

    assert isinstance(ans, list)
    assert len(ans) == (parallel_calls * num_calls) ** (depth + 1)
    assert all([0 < x < 1 for x in ans])

    r_h = finished_result.request_heap
    assert len(r_h.insertion_request) ==  1
    child_requests = r_h.children(r_h.insertion_request[0].sink_id)

    assert len(child_requests) == num_calls * parallel_calls
    for r in child_requests:
        assert r.input[0][0] == num_calls
        assert r.input[0][1] == parallel_calls
        assert 0 < r.input[0][2] < depth


@pytest.mark.timeout(4)
def test_nested_no_deadlock():
    num_calls = 2
    parallel_calls = 2
    depth = 3

    nested_many_calls_tester(num_calls, parallel_calls, depth)


def test_nested_no_deadlock_harder():
    num_calls = 1
    parallel_calls = 3
    depth = 3

    nested_many_calls_tester(num_calls, parallel_calls, depth)


def test_nested_no_deadlock_harder_2():
    num_calls = 3
    parallel_calls = 1
    depth = 3

    nested_many_calls_tester(num_calls, parallel_calls, depth)


def test_multiple_runs():
    with rc.Runner(executor_config=rc.ExecutorConfig(logging_setting="NONE")) as run:
        result = run.run_sync(RNGNode)
        assert 0 < result.answer < 1

        result = run.run_sync(RNGNode)


        info = run.info
        assert isinstance(info.answer, List)
        assert 0 < info.answer[0] < 1
        assert 0 < info.answer[1] < 1

        insertion_requests = info.request_heap.insertion_request

        assert isinstance(insertion_requests, List)
        assert len(insertion_requests) == 2
        for i_r in insertion_requests:
            i_r_id = i_r.identifier

            subset_info = info.get_info(i_r_id)
            assert 0 < subset_info.answer < 1
            assert len(subset_info.node_heap.heap()) == 1

@pytest.mark.asyncio
async def test_multiple_runs_async():
    with rc.Runner(executor_config=rc.ExecutorConfig(logging_setting="NONE")) as run:
        result = await run.run(RNGNode)
        assert 0 < result.answer < 1

        result = await run.run(RNGNode)
        assert isinstance(result.answer, List)
        assert 0 < result.answer[0] < 1
        assert 0 < result.answer[1] < 1

        info = run.info

        insertion_requests = info.request_heap.insertion_request

        assert isinstance(insertion_requests, List)
        assert len(insertion_requests) == 2
        for i_r in insertion_requests:
            i_r_id = i_r.identifier

            subset_info = info.get_info(i_r_id)
            assert 0 < subset_info.answer < 1
            assert len(subset_info.node_heap.heap()) == 1

def level_3(message: str):
    return message

Level3 = rc.library.from_function(level_3)

async def a_level_2(message: str):
    return await rc.call(Level3, message)

def level_2(message: str):
    return rc.call_sync(Level3, message)

ALevel2 = rc.library.from_function(a_level_2)
Level2 = rc.library.from_function(level_2)

@pytest.mark.parametrize("level_2_node", [Level2, ALevel2], ids=["sync", "async"])
def test_multi_level_calls(level_2_node):
    async def level_1_async(message: str):
        return await rc.call(level_2_node, message)

    def level_1(message: str):
        return rc.call_sync(level_2_node, message)

    ALevel1 = rc.library.from_function(level_1_async)
    Level1 = rc.library.from_function(level_1)

    with rc.Runner(executor_config=rc.ExecutorConfig(logging_setting="NONE")) as run:
        result = run.run_sync(Level1, "Hello from Level 1")
        assert result.answer == "Hello from Level 1"

    with rc.Runner(executor_config=rc.ExecutorConfig(logging_setting="NONE")):
        result = rc.call_sync(ALevel1, "Hello from Level 1 (async)")
        assert result == "Hello from Level 1 (async)"

    with rc.Runner(executor_config=rc.ExecutorConfig(logging_setting="NONE")) as run:
        result = rc.call_sync(Level1, "Hello from Level 1")
        assert result == "Hello from Level 1"

    with rc.Runner(executor_config=rc.ExecutorConfig(logging_setting="NONE")) as run:
        result = run.run_sync(ALevel1, "Hello from Level 1 (async)")
        assert result.answer == "Hello from Level 1 (async)"


@pytest.mark.parametrize("level_2_node", [Level2, ALevel2], ids=["sync", "async"])
@pytest.mark.asyncio
async def test_multi_level_calls(level_2_node):
    async def level_1_async(message: str):
        return await rc.call(level_2_node, message)

    def level_1(message: str):
        return rc.call_sync(level_2_node, message)

    ALevel1 = rc.library.from_function(level_1_async)
    Level1 = rc.library.from_function(level_1)

    with rc.Runner(executor_config=rc.ExecutorConfig(logging_setting="NONE")) as run:
        result = await run.run(Level1, "Hello from Level 1")
        assert result.answer == "Hello from Level 1"

    with rc.Runner(executor_config=rc.ExecutorConfig(logging_setting="NONE")):
        result = await rc.call(ALevel1, "Hello from Level 1 (async)")
        assert result == "Hello from Level 1 (async)"

    with rc.Runner(executor_config=rc.ExecutorConfig(logging_setting="NONE")) as run:
        result = await rc.call(Level1, "Hello from Level 1")
        assert result == "Hello from Level 1"

    with rc.Runner(executor_config=rc.ExecutorConfig(logging_setting="NONE")) as run:
        result = await run.run(ALevel1, "Hello from Level 1 (async)")
        assert result.answer == "Hello from Level 1 (async)"



async def timeout_node(timeout_len: float):
    """
    A node that sleeps for the given timeout length.
    """
    await asyncio.sleep(timeout_len)
    return timeout_len


TimeoutNode = rc.library.from_function(timeout_node)


def test_timeout():
    with rc.Runner(
        executor_config=rc.ExecutorConfig(logging_setting="NONE", timeout=0.1)
    ) as run:
        with pytest.raises(GlobalTimeOutError):
            run.run_sync(TimeoutNode, 0.3)


async def timeout_thrower():
    raise asyncio.TimeoutError("Test timeout error")


TimeoutThrower = rc.library.from_function(timeout_thrower)


def test_timeout_thrower():
    with rc.Runner(executor_config=rc.ExecutorConfig(logging_setting="NONE")) as run:
        try:
            result = run.run_sync(TimeoutThrower)
        except Exception as e:
            assert isinstance(e, asyncio.TimeoutError)
