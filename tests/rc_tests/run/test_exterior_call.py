import requestcompletion as rc
import random
import pytest
import time
import asyncio
import concurrent.futures

RNGNode = rc.library.from_function(random.random)


def sleep(timeout_len: float):
    time.sleep(timeout_len)
    return timeout_len


def exception_node():
    raise Exception()


TimeoutNode = rc.library.from_function(sleep)
ExceptionNode = rc.library.from_function(exception_node)


@pytest.mark.asyncio
async def test_runner_call_basic():
    response = await rc.call(RNGNode)

    assert isinstance(response, float), "Expected a float result from RNGNode"


async def test_runner_call_with_context():
    with rc.Runner() as run:
        response = await rc.call(RNGNode)
        assert isinstance(response, float), "Expected a float result from RNGNode"
        info = run.info
        assert info.answer == response, (
            "Expected the answer to be the same as the response"
        )


async def logging_config_test_async():
    async def run_with_logging_config(log_setting):
        rc.set_config(rc.ExecutorConfig(end_on_error=True))
        with pytest.raises(Exception):
            resp = await rc.call(ExceptionNode)
            print(resp)

    async def run_with_logging_config_w_context(log_setting):
        rc.set_config(rc.ExecutorConfig(logging_setting=log_setting))
        with rc.Runner() as run:
            info = await run.run(RNGNode)
            runner = rc.run.get_runner()
            assert run == runner
            assert runner.rc_state.executor_config.logging_setting == log_setting
            assert runner.rc_state.executor_config.end_on_error == False

        response = info.answer
        assert isinstance(response, float), "Expected a float result from RNGNode"
        assert 0 < response < 1, "Expected a float result from RNGNode"
        assert info.answer == response, (
            "Expected the answer to be the same as the response"
        )

    async def run_with_logging_config_w_context_w_call(log_setting):
        rc.set_config(rc.ExecutorConfig(logging_setting=log_setting))
        with rc.Runner() as run:
            resp = await rc.call(RNGNode)
            info = run.info
            runner = rc.run.get_runner()
            assert run == runner
            assert runner.rc_state.executor_config.logging_setting == log_setting
            assert runner.rc_state.executor_config.end_on_error == False

        assert isinstance(resp, float), "Expected a float result from RNGNode"
        assert 0 < resp < 1, "Expected a float result from RNGNode"
        assert info.answer == resp, "Expected the answer to be the same as the response"

    for config in ["VERBOSE", "QUIET", "REGULAR", "NONE"]:
        await run_with_logging_config(config)
        await run_with_logging_config_w_context(config)
        await run_with_logging_config_w_context_w_call(config)

    # do it in parallel here,
    options = ["VERBOSE", "QUIET", "REGULAR", "NONE"]
    contracts = [run_with_logging_config(config) for config in options]
    await asyncio.gather(*contracts)

    contracts = [run_with_logging_config_w_context(config) for config in options]
    await asyncio.gather(*contracts)

    contracts = [run_with_logging_config_w_context_w_call(config) for config in options]
    await asyncio.gather(*contracts)


async def test_different_config_global_set_async():
    rc.set_config(rc.ExecutorConfig(end_on_error=False))
    await logging_config_test_async()


async def test_different_config_local_set_async():
    await logging_config_test_async()


def logging_config_test_threads():
    def run_with_logging_config_w_context(log_setting):
        rc.set_config(rc.ExecutorConfig(logging_setting=log_setting))
        with rc.Runner() as run:
            info = run.run_sync(RNGNode)
            runner = rc.run.get_runner()
            assert run == runner
            assert runner.rc_state.executor_config.logging_setting == log_setting
            assert runner.rc_state.executor_config.end_on_error == False

        response = info.answer
        assert isinstance(response, float), "Expected a float result from RNGNode"
        assert 0 < response < 1, "Expected a float result from RNGNode"
        assert info.answer == response, (
            "Expected the answer to be the same as the response"
        )

    with concurrent.futures.ThreadPoolExecutor() as executor:
        executor.map(
            run_with_logging_config_w_context, ["VERBOSE", "QUIET", "REGULAR", "NONE"]
        )


def test_threads_config():
    logging_config_test_threads()


def test_sequence_of_changes():
    rc.set_config(rc.ExecutorConfig(end_on_error=True))
    rc.set_config(rc.ExecutorConfig(end_on_error=False))
    rc.set_config(rc.ExecutorConfig(end_on_error=True, logging_setting="NONE"))
    with rc.Runner() as run:
        info = run.run_sync(RNGNode)
        assert run.rc_state.executor_config.end_on_error
        assert run.rc_state.executor_config.logging_setting == "NONE"
        assert info.answer == run.info.answer


def test_sequence_of_changes_overwrite():
    rc.set_config(rc.ExecutorConfig(end_on_error=True))
    rc.set_config(rc.ExecutorConfig(end_on_error=False))
    with rc.Runner(
        executor_config=rc.ExecutorConfig(end_on_error=True, logging_setting="NONE")
    ) as run:
        info = run.run_sync(RNGNode)
        assert run.rc_state.executor_config.end_on_error
        assert run.rc_state.executor_config.logging_setting == "NONE"
        assert info.answer == run.info.answer


message = "Hello, World!"


def streaming_func():
    rc.stream(message)
    return


class StreamHandler:
    def __init__(self):
        self.message = []

    def handle(self, item: str) -> None:
        self.message.append(item)


StreamingNode = rc.library.from_function(streaming_func)


def test_streaming_inserted_globally():
    handler = StreamHandler()

    rc.set_streamer(handler.handle)
    with rc.Runner() as run:
        result = run.run_sync(StreamingNode)
        assert result.answer == None

    sleep(0.1)
    assert len(handler.message) == 1
    assert handler.message[0] == message


def test_streaming_inserted_locally():
    handler = StreamHandler()

    with rc.Runner(subscriber=handler.handle) as run:
        result = run.run_sync(StreamingNode)
        assert result.answer == None

    sleep(0.1)
    assert len(handler.message) == 1
    assert handler.message[0] == message


def fake_handler(item: str) -> None:
    raise Exception("This is a fake handler")


def test_streaming_overwrite():
    handler = StreamHandler()

    rc.set_streamer(fake_handler)
    with rc.Runner(subscriber=handler.handle) as run:
        result = run.run_sync(StreamingNode)
        assert result.answer == None

    sleep(0.1)
    assert len(handler.message) == 1
    assert handler.message[0] == message
