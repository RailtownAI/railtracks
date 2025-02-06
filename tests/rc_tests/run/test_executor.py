from __future__ import annotations

import time

from requestcompletion.run.config import ExecutorConfig
from requestcompletion.run.run import run

from tests.rc_tests.fixtures.nodes import (
    CallNode,
    RNGNode,
)


def test_no_deadlock():
    num_calls = 4
    parallel_calls = 55
    t = time.time()
    i_node = CallNode(num_calls, parallel_calls, lambda: RNGNode())
    finished_result = run(
        i_node,
        executor_config=ExecutorConfig(
            global_num_retries=350,
            workers=5,
            timeout=250,
        ),
    )

    assert isinstance(finished_result.answer, list)

    assert len(finished_result.answer) == num_calls * parallel_calls
    assert all([0 < x < 1 for x in finished_result.answer])


def test_small_no_deadlock():
    num_calls = 10
    parallel_calls = 15

    i_node = CallNode(num_calls, parallel_calls, lambda: RNGNode())
    finished_result = run(
        i_node,
        executor_config=ExecutorConfig(
            global_num_retries=350,
            workers=5,
            timeout=250,
        ),
    )

    assert isinstance(finished_result.answer, list)

    assert len(finished_result.answer) == num_calls * parallel_calls
    assert all([0 < x < 1 for x in finished_result.answer])


def test_large_no_deadlock():
    num_calls = 45
    parallel_calls = 23

    i_node = CallNode(num_calls, parallel_calls, lambda: RNGNode())
    finished_result = run(
        i_node,
        executor_config=ExecutorConfig(
            global_num_retries=350,
            workers=5,
            timeout=250,
        ),
    )

    assert isinstance(finished_result.answer, list)

    assert len(finished_result.answer) == num_calls * parallel_calls
    assert all([0 < x < 1 for x in finished_result.answer])


def test_simple_rng_graph():
    i_r = RNGNode()
    finished_result = run(i_r)

    assert isinstance(finished_result.answer, float)

    assert 0 < finished_result.answer < 1
