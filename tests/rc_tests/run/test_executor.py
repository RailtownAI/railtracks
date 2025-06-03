from __future__ import annotations

import asyncio
import random

import pytest
import requestcompletion as rc


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
    with rc.Runner() as run:
        finished_result = run.run_sync(ManyCalls, num_calls, parallel_calls)

    ans = finished_result.answer

    assert isinstance(ans, list)
    assert len(ans) == num_calls * parallel_calls
    assert all([0 < x < 1 for x in ans])


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
    with rc.Runner() as run:
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
    with rc.Runner() as run:
        finished_result = run.run_sync(
            NestedManyCalls, num_calls, parallel_calls, depth
        )

    ans = finished_result.answer

    assert isinstance(ans, list)
    assert len(ans) == (parallel_calls * num_calls) ** (depth + 1)
    assert all([0 < x < 1 for x in ans])

    r_h = finished_result.request_heap
    child_requests = r_h.children(r_h.insertion_request.sink_id)

    assert len(child_requests) == num_calls * parallel_calls
    for r in child_requests:
        assert r.input[0][0] == num_calls
        assert r.input[0][1] == parallel_calls
        assert 0 < r.input[0][2] < depth


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
    with rc.Runner() as run:
        result = run.run_sync(RNGNode)
        assert 0 < result.answer < 1
        with pytest.raises(RuntimeError):
            run.run_sync(RNGNode)
