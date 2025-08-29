import time

import pytest
import railtracks as rt


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "timeout_config, expected, buffer",
    [
        ([1, 2, 3, 2, 1], 3.5, 0.75),
        ([1, 5, 1], 5.25, 0.5),
        ([1] * 35, 1.25, 0.5),
        ([2] * 100 + [3] * 50, 3.5, 1),
        ([10], 10.25, 0.5),
    ],
)
async def test_parallel_calls(parallel_node, timeout_config, expected, buffer):
    with rt.Session(
        logging_setting="NONE",
    ):
        start_time = time.time()
        results = await rt.call(parallel_node, timeout_config)
        assert abs(time.time() - start_time - expected) < buffer
        assert results == timeout_config


exc = ValueError("This is a test exception")


async def error_thrower(exception: Exception, is_throw):
    if is_throw:
        raise exception

    return None


ErrorThrower = rt.function_node(error_thrower)


async def error_thrower_top_level(
    num_times: int, return_exceptions: bool | None = None
):
    if return_exceptions is None:
        results = await rt.call_batch(
            ErrorThrower,
            [exc] * num_times,
            [
                False,
            ]
            * (num_times - 1)
            + [True],  # Last one should throw an error,
        )
    else:
        results = await rt.call_batch(
            ErrorThrower,
            [exc] * num_times,
            [
                False,
            ]
            * (num_times - 1)
            + [True],  # Last one should throw an error,
            return_exceptions=return_exceptions,
        )

    if return_exceptions is None or return_exceptions:
        assert len(results) == num_times
        assert isinstance(results[-1], type(exc)), (
            "The last result should be the exception"
        )
        assert all(result is None for result in results[:-1]), (
            "All other results should be None"
        )
    else:
        # if they have set return_exceptions=False, then exceptions should have already been raised
        pass


ErrorThrowerTopLevel = rt.function_node(error_thrower_top_level)


@pytest.mark.parametrize(
    "num_times", [1, 2, 3, 5, 10, 20], ids=lambda x: f"num_times={x}"
)
@pytest.mark.asyncio
async def test_batch_error_handling_default_error_prop(num_times):
    """
    Test that batch execution handles errors correctly.
    """
    with rt.Session(
        logging_setting="NONE",
    ):
        await rt.call(ErrorThrowerTopLevel, num_times=num_times)


@pytest.mark.parametrize(
    "num_times", [1, 2, 3, 5, 10, 20], ids=lambda x: f"num_times={x}"
)
@pytest.mark.asyncio
async def test_batch_error_handling_true_error_prop(num_times):
    """
    Test that batch execution handles errors correctly.
    """
    with rt.Session(
        logging_setting="NONE",
    ):
        await rt.call(ErrorThrowerTopLevel, num_times=num_times, return_exceptions=True)


@pytest.mark.parametrize(
    "num_times", [1, 2, 3, 5, 10, 20], ids=lambda x: f"num_times={x}"
)
@pytest.mark.asyncio
async def test_batch_error_handling_false_error_prop(num_times):
    """
    Test that batch execution handles errors correctly.
    """
    with rt.Session(
        logging_setting="NONE",
    ):
        with pytest.raises(type(exc)):
            await rt.call(
                ErrorThrowerTopLevel, num_times=num_times, return_exceptions=False
            )
