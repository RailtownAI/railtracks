import railtracks as rt
import random
import pytest
import time
import asyncio
import concurrent.futures

import railtracks.context.central
import railtracks.interaction.broadcast_
from railtracks import ExecutorConfig

RNGNode = rt.function_node(random.random)


def sleep(timeout_len: float):
    time.sleep(timeout_len)
    return timeout_len


def exception_node():
    raise Exception()


TimeoutNode = rt.function_node(sleep)
ExceptionNode = rt.function_node(exception_node)


@pytest.mark.asyncio
async def test_runner_call_basic():
    response = await rt.call(RNGNode)

    assert isinstance(response, float), "Expected a float result from RNGNode"


@pytest.mark.skip(reason="Skipping test for now, will be fixed in future release")
async def test_runner_call_with_context():
    with rt.Session() as run:
        response = await rt.call(RNGNode)
        assert isinstance(response, float), "Expected a float result from RNGNode"
        info = run.info
        assert (
            info.answer == response
        ), "Expected the answer to be the same as the response"


async def logging_config_test_async():
    async def run_with_logging_config(log_setting):
        railtracks.context.central.set_config(
            end_on_error=True
        )
        with pytest.raises(Exception):
            resp = await rt.call(ExceptionNode)


    async def run_with_logging_config_w_context(log_setting):
        railtracks.context.central.set_config(end_on_error=False)
        railtracks.context.central.set_config(
            logging_setting=log_setting
        )
        with rt.Session() as run:
            info = await rt.call(RNGNode)
            runner = run
            assert run == runner
            assert runner.rt_state.executor_config.logging_setting == log_setting
            assert runner.rt_state.executor_config.end_on_error == False

        response = info
        assert isinstance(response, float), "Expected a float result from RNGNode"
        assert 0 < response < 1, "Expected a float result from RNGNode"
        assert (
            info == response
        ), "Expected the answer to be the same as the response"

    async def run_with_logging_config_w_context_w_call(log_setting):
        railtracks.context.central.set_config(
            logging_setting=log_setting
        )
        with rt.Session() as run:
            resp = await rt.call(RNGNode)
            info = run.info
            runner = run
            assert run == runner
            assert runner.rt_state.executor_config.logging_setting == log_setting
            assert runner.rt_state.executor_config.end_on_error == False

        assert isinstance(resp, float), "Expected a float result from RNGNode"
        assert 0 < resp < 1, "Expected a float result from RNGNode"
        assert info.answer == resp, "Expected the answer to be the same as the response"

    for config in ["VERBOSE", "QUIET", "REGULAR", "NONE"]:
        await run_with_logging_config(config)
        await run_with_logging_config_w_context(config)
        # await run_with_logging_config_w_context_w_call(config)

    # do it in parallel here,
    options = ["VERBOSE", "QUIET", "REGULAR", "NONE"]
    contracts = [run_with_logging_config(config) for config in options]
    await asyncio.gather(*contracts)

    contracts = [run_with_logging_config_w_context(config) for config in options]
    await asyncio.gather(*contracts)

    # contracts = [run_with_logging_config_w_context_w_call(config) for config in options]
    # await asyncio.gather(*contracts)


async def test_different_config_global_set_async():
    railtracks.context.central.set_config(end_on_error=False)
    await logging_config_test_async()


async def test_different_config_local_set_async():
    await logging_config_test_async()


def logging_config_test_threads():
    def run_with_logging_config_w_context(log_setting):
        railtracks.context.central.set_config(
            logging_setting=log_setting
        )
        with rt.Session() as run:
            response = rt.call_sync(RNGNode)
            runner = run
            assert runner.rt_state.executor_config.logging_setting == log_setting
            assert runner.rt_state.executor_config.end_on_error == False

        assert isinstance(response, float), "Expected a float result from RNGNode"
        assert 0 < response < 1, "Expected a float result from RNGNode"


    with concurrent.futures.ThreadPoolExecutor() as executor:
        executor.map(
            run_with_logging_config_w_context, ["VERBOSE", "QUIET", "REGULAR", "NONE"]
        )


def test_threads_config():
    logging_config_test_threads()


def test_sequence_of_changes():
    railtracks.context.central.set_config(end_on_error=True)
    railtracks.context.central.set_config(end_on_error=False)
    railtracks.context.central.set_config(
        end_on_error=True, logging_setting="NONE"
    )
    with rt.Session() as run:
        response = rt.call_sync(RNGNode)
        assert run.rt_state.executor_config.end_on_error
        assert run.rt_state.executor_config.logging_setting == "NONE"
        assert response == run.info.answer


def test_sequence_of_changes_overwrite():
    railtracks.context.central.set_config(end_on_error=True)
    railtracks.context.central.set_config(end_on_error=False)
    with rt.Session(
        end_on_error=True, logging_setting="NONE"
    ) as run:
        response = rt.call_sync(RNGNode)
        assert run.rt_state.executor_config.end_on_error
        assert run.rt_state.executor_config.logging_setting == "NONE"
        assert response == run.info.answer

def test_back_to_defaults():
    rt.set_config(end_on_error=True, logging_setting="REGULAR")
    with rt.Session(
        end_on_error=True, logging_setting="NONE"
    ) as run:
        assert run.rt_state.executor_config.end_on_error
        assert run.rt_state.executor_config.logging_setting == "NONE"

    with rt.Session() as run:
        assert run.rt_state.executor_config.end_on_error
        assert run.rt_state.executor_config.logging_setting == "REGULAR"




message = "Hello, World!"


async def streaming_func():
    await railtracks.interaction.broadcast(message)
    return


class StreamHandler:
    def __init__(self):
        self.message = []

    def handle(self, item: str) -> None:
        self.message.append(item)


StreamingNode = rt.function_node(streaming_func)


def test_streaming_inserted_globally():
    handler = StreamHandler()

    railtracks.context.central.set_config(broadcast_callback=handler.handle)
    with rt.Session() as run:
        result = rt.call_sync(StreamingNode)
        assert result is None

    sleep(0.1)
    assert len(handler.message) == 1
    assert handler.message[0] == message


def test_streaming_inserted_locally():
    handler = StreamHandler()

    with rt.Session(broadcast_callback=handler.handle) as run:
        result = rt.call_sync(StreamingNode)
        assert result is None

    sleep(0.1)
    assert len(handler.message) == 1
    assert handler.message[0] == message


def fake_handler(item: str) -> None:
    raise Exception("This is a fake handler")


def test_streaming_overwrite():
    handler = StreamHandler()

    railtracks.context.central.set_config(broadcast_callback=fake_handler)
    with rt.Session(broadcast_callback=handler.handle) as run:
        result = rt.call_sync(StreamingNode)
        assert result is None

    sleep(0.1)
    assert len(handler.message) == 1
    assert handler.message[0] == message
