from __future__ import annotations

import asyncio
import random

import pytest
import railtracks as rt
from railtracks.state.request import Failure

RNGNode = rt.function_node(random.random)


@pytest.mark.timeout(1)
async def test_simple_request():
    with rt.Session(logging_setting="NONE"):
        result = await rt.call(RNGNode)

    assert isinstance(result, float)
    assert 0 < result < 1


class CustomTestError(Exception):
    pass


async def error_thrower():
    raise CustomTestError("This is a test error")


ErrorThrower = rt.function_node(error_thrower)


async def test_error():
    with rt.Session(logging_setting="NONE"):
        with pytest.raises(CustomTestError):
            await rt.call(ErrorThrower)


async def error_handler():
    try:
        await rt.call(ErrorThrower)
    except CustomTestError:
        return "Caught the error"


ErrorHandler = rt.function_node(error_handler)


@pytest.mark.timeout(1)
async def test_error_handler():
    with rt.Session(logging_setting="NONE"):
        result = await rt.call(ErrorHandler)
    assert result == "Caught the error"


async def test_error_handler_wo_retry():
    with pytest.raises(CustomTestError):
        with rt.Session(end_on_error=True, logging_setting="NONE"):
            await rt.call(ErrorHandler)


async def error_handler_with_retry(retries: int):
    for _ in range(retries):
        try:
            return await rt.call(ErrorThrower)
        except CustomTestError:
            continue

    return "Caught the error"


ErrorHandlerWithRetry = rt.function_node(error_handler_with_retry)


@pytest.mark.timeout(5)
async def test_error_handler_with_retry():
    for num_retries in range(5, 15):
        with rt.Session(logging_setting="NONE") as run:
            result = await rt.call(ErrorHandlerWithRetry, num_retries)
            result = run.info

        assert result.answer == "Caught the error"
        i_r = result.request_forest.insertion_request[0]

        children = result.request_forest.children(i_r.sink_id)
        assert len(children) == num_retries

        for r in children:
            assert isinstance(r.output, Failure)
            assert isinstance(r.output.exception, CustomTestError)


async def parallel_error_handler(num_calls: int, parallel_calls: int):
    data = []
    for _ in range(num_calls):
        contracts = [rt.call(ErrorThrower) for _ in range(parallel_calls)]

        results = await asyncio.gather(*contracts, return_exceptions=True)

        data += results

    return data


ParallelErrorHandler = rt.function_node(parallel_error_handler)


async def test_parallel_error_tester():
    for n_c, p_c in [(10, 10), (3, 20), (1, 10), (60, 10)]:
        with rt.Session(logging_setting="NONE"):
            result = await rt.call(ParallelErrorHandler, n_c, p_c)

        assert isinstance(result, list)
        assert len(result) == n_c * p_c
        assert all(isinstance(x, CustomTestError) for x in result)


# wraps the above error handler in a top level function
async def error_handler_wrapper(num_calls: int, parallel_calls: int):
    try:
        return await rt.call(ParallelErrorHandler, num_calls, parallel_calls)
    except CustomTestError:
        return "Caught the error"


ErrorHandlerWrapper = rt.function_node(error_handler_wrapper)


async def test_parallel_error_wrapper():
    for n_c, p_c in [(10, 10), (3, 20), (1, 10), (60, 10)]:
        with rt.Session(logging_setting="NONE") as run:
            result = await rt.call(ErrorHandlerWrapper, n_c, p_c)

        assert len(result) == n_c * p_c
        assert all(isinstance(x, CustomTestError) for x in result)
        i_r = run.info.request_forest.insertion_request[0]

        children = run.info.request_forest.children(i_r.sink_id)
        assert len(children) == 1
        full_children = run.info.request_forest.children(children[0].sink_id)
        for r in children:
            assert r.output == result

        for r in full_children:
            assert isinstance(r.output, Failure)
            assert isinstance(r.output.exception, CustomTestError)
