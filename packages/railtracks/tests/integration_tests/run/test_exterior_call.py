import asyncio
import concurrent.futures
import random
import time

import pytest
import railtracks as rt
import railtracks.context.central
import railtracks.interaction.broadcast_

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
        assert info.answer == response, (
            "Expected the answer to be the same as the response"
        )


async def logging_config_test_async():
    async def run_with_logging_config(log_setting):
        railtracks.context.central.set_config(end_on_error=True)
        with pytest.raises(Exception):
            await rt.call(ExceptionNode)

    async def run_with_logging_config_w_context(log_setting):
        railtracks.context.central.set_config(end_on_error=False)
        railtracks.context.central.set_config(logging_setting=log_setting)
        with rt.Session() as session:
            info = await rt.call(RNGNode)

            assert session.rt_state.executor_config.logging_setting == log_setting
            assert not session.rt_state.executor_config.end_on_error

        response = info
        assert isinstance(response, float), "Expected a float result from RNGNode"
        assert 0 < response < 1, "Expected a float result from RNGNode"
        assert info == response, "Expected the answer to be the same as the response"

    async def run_with_logging_config_w_context_w_call(log_setting):
        railtracks.context.central.set_config(logging_setting=log_setting)
        with rt.Session() as session:
            resp = await rt.call(RNGNode)
            info = session.info

            assert session.rt_state.executor_config.logging_setting == log_setting
            assert not session.rt_state.executor_config.end_on_error

        assert isinstance(resp, float), "Expected a float result from RNGNode"
        assert 0 < resp < 1, "Expected a float result from RNGNode"
        assert info.answer == resp, "Expected the answer to be the same as the response"

    for config in ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL", "NONE"]:
        await run_with_logging_config(config)
        await run_with_logging_config_w_context(config)
        # await run_with_logging_config_w_context_w_call(config)

    # do it in parallel here,
    options = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL", "NONE"]
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
    async def run_with_logging_config_w_context(log_setting):
        railtracks.context.central.set_config(logging_setting=log_setting)
        with rt.Session() as session:
            response = await rt.call(RNGNode)
            assert session.rt_state.executor_config.logging_setting == log_setting
            assert not session.rt_state.executor_config.end_on_error

        assert isinstance(response, float), "Expected a float result from RNGNode"
        assert 0 < response < 1, "Expected a float result from RNGNode"
    
    def run_with_logging_config(log_setting):
        asyncio.run(run_with_logging_config_w_context(log_setting))
    
    with concurrent.futures.ThreadPoolExecutor() as executor:
        executor.map(
            run_with_logging_config, ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL", "NONE"]
        )


def test_threads_config():
    logging_config_test_threads()


async def test_sequence_of_changes():
    railtracks.context.central.set_config(end_on_error=True)
    railtracks.context.central.set_config(end_on_error=False)
    railtracks.context.central.set_config(end_on_error=True, logging_setting="NONE")
    with rt.Session() as session:
        response = await rt.call(RNGNode)
        assert session.rt_state.executor_config.end_on_error
        assert session.rt_state.executor_config.logging_setting == "NONE"
        assert response == session.info.answer


async def test_sequence_of_changes_overwrite():
    railtracks.context.central.set_config(end_on_error=True)
    railtracks.context.central.set_config(end_on_error=False)
    with rt.Session(end_on_error=True, logging_setting="NONE") as session:
        response = await rt.call(RNGNode)
        assert session.rt_state.executor_config.end_on_error
        assert session.rt_state.executor_config.logging_setting == "NONE"
        assert response == session.info.answer


def test_back_to_defaults():
    rt.set_config(end_on_error=True, logging_setting="INFO")
    with rt.Session(end_on_error=True, logging_setting="NONE") as run:
        assert run.rt_state.executor_config.end_on_error
        assert run.rt_state.executor_config.logging_setting == "NONE"

    with rt.Session() as run:
        assert run.rt_state.executor_config.end_on_error
        assert run.rt_state.executor_config.logging_setting == "INFO"


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


async def test_streaming_inserted_globally():
    handler = StreamHandler()

    railtracks.context.central.set_config(broadcast_callback=handler.handle)
    with rt.Session():
        result = await rt.call(StreamingNode)
        assert result is None

    sleep(0.1)
    assert len(handler.message) == 1
    assert handler.message[0] == message


async def test_streaming_inserted_locally():
    handler = StreamHandler()

    with rt.Session(broadcast_callback=handler.handle):
        result = await rt.call(StreamingNode)
        assert result is None

    sleep(0.1)
    assert len(handler.message) == 1
    assert handler.message[0] == message


def fake_handler(item: str) -> None:
    raise Exception("This is a fake handler")


async def test_streaming_overwrite():
    handler = StreamHandler()

    railtracks.context.central.set_config(broadcast_callback=fake_handler)
    with rt.Session(broadcast_callback=handler.handle):
        result = await rt.call(StreamingNode)
        assert result is None

    sleep(0.1)
    assert len(handler.message) == 1
    assert handler.message[0] == message
