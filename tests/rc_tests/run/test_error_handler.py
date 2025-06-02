from __future__ import annotations

import asyncio

import pytest
import random

import src.requestcompletion as rc

from src.requestcompletion.state.request import Failure

RNGNode = rc.library.from_function(random.random)


def test_simple_request():
    with rc.Runner() as run:
        result = run.run_sync(RNGNode)

    assert isinstance(result.answer, float)
    assert 0 < result.answer < 1


class TestError(Exception):
    pass


async def error_thrower():
    raise TestError("This is a test error")


ErrorThrower = rc.library.from_function(error_thrower)


def test_error():
    with rc.Runner() as run:
        with pytest.raises(TestError):
            run.run_sync(ErrorThrower)


async def error_handler():
    try:
        answer = await rc.call(ErrorThrower)
    except TestError as e:
        return "Caught the error"


ErrorHandler = rc.library.from_function(error_handler)


def test_error_handler():
    with rc.Runner() as run:
        result = run.run_sync(ErrorHandler)
    assert result.answer == "Caught the error"


def test_error_handler_wo_retry():
    with pytest.raises(rc.state.execute.ExecutionException):
        with rc.Runner(executor_config=rc.ExecutorConfig(end_on_error=True)) as run:
            result = run.run_sync(ErrorHandler)


async def error_handler_with_retry(retries: int):
    for _ in range(retries):
        try:
            return await rc.call(ErrorThrower)
        except TestError as e:
            continue

    return "Caught the error"


ErrorHandlerWithRetry = rc.library.from_function(error_handler_with_retry)


def test_error_handler_with_retry():
    for num_retries in range(5, 15):
        with rc.Runner() as run:
            result = run.run_sync(ErrorHandlerWithRetry, num_retries)

        assert result.answer == "Caught the error"
        i_r = result.request_heap.insertion_request

        children = result.request_heap.children(i_r.sink_id)
        assert len(children) == num_retries

        for r in children:
            assert isinstance(r.output, Failure)
            assert isinstance(r.output.exception, TestError)

        assert all([isinstance(e, TestError) for e in result.exception_history])
        assert len(result.exception_history) == num_retries


async def parallel_error_handler(num_calls: int, parallel_calls: int):
    data = []
    for _ in range(num_calls):
        contracts = [rc.call(ErrorThrower) for _ in range(parallel_calls)]

        results = await asyncio.gather(*contracts, return_exceptions=True)

        data += results

    return data


ParallelErrorHandler = rc.library.from_function(parallel_error_handler)


def test_parallel_error_tester():

    for n_c, p_c in [(10, 10), (3, 20), (1, 10), (60, 10)]:
        with rc.Runner() as run:
            result = run.run_sync(ParallelErrorHandler, n_c, p_c)

        assert isinstance(result.answer, list)
        assert len(result.answer) == n_c * p_c
        assert all([isinstance(x, TestError) for x in result.answer])


# wraps the above error handler in a top level function
async def error_handler_wrapper(num_calls: int, parallel_calls: int):
    try:
        return await rc.call(ParallelErrorHandler, num_calls, parallel_calls)
    except TestError as e:
        return "Caught the error"


ErrorHandlerWrapper = rc.library.from_function(error_handler_wrapper)


def test_parallel_error_wrapper():
    for n_c, p_c in [(10, 10), (3, 20), (1, 10), (60, 10)]:
        with rc.Runner() as run:
            result = run.run_sync(ErrorHandlerWrapper, n_c, p_c)

        assert len(result.answer) == n_c * p_c
        assert all([isinstance(x, TestError) for x in result.answer])

        i_r = result.request_heap.insertion_request

        children = result.request_heap.children(i_r.sink_id)
        assert len(children) == 1
        full_children = result.request_heap.children(children[0].sink_id)

        for r in children:
            assert r.output == result.answer

        for r in full_children:
            assert isinstance(r.output, Failure)
            assert isinstance(r.output.exception, TestError)

        assert all([isinstance(e, TestError) for e in result.exception_history])
        assert len(result.exception_history) == n_c * p_c
