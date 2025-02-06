import concurrent.futures

import pytest

from requestcompletion.context.context import EmptyContext
from requestcompletion.run.info import ExecutionInfo
from requestcompletion.run.config import ExecutorConfig
from requestcompletion.run.run import run

from tests.rc_tests.fixtures.nodes import (
    RNGNode,
)

## this code is commented out


def run_check_executors(num_processes: int):
    with concurrent.futures.ThreadPoolExecutor() as executor:
        futures = []
        for _ in range(num_processes):
            i_r = RNGNode()
            futures.append(
                executor.submit(
                    lambda: run(
                        start_node=i_r,
                        context=EmptyContext(),
                        executor_config=ExecutorConfig(global_num_retries=5),
                    )
                )
            )

        for f in concurrent.futures.as_completed(futures):
            result: ExecutionInfo = f.result()
            assert isinstance(result.answer, float)
            assert 0 < result.answer < 1


@pytest.mark.skip(
    "This test will not work with out current mechanism for handling multiple runs"
)
def test_many_executors():
    run_check_executors(10)


@pytest.mark.skip(
    "This test will not work with out current mechanism for handling multiple runs"
)
def test_crazy_amount_executors():
    run_check_executors(1000)
