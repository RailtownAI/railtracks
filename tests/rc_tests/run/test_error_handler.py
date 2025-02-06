from __future__ import annotations

import pytest

import requestcompletion.nodes.nodes as no
from requestcompletion.run.config import ExecutorConfig
from requestcompletion.run.run import run

from requestcompletion.run.state.execute import (
    GlobalTimeOut,
    GlobalRetriesExceeded,
    ExecutionException,
)

from requestcompletion.exceptions import (
    NodeException,
    FatalException,
    ResetException,
)
from tests.rc_tests.fixtures.nodes import (
    RNGNode,
    FatalErrorNode,
    REGULAR_ERROR,
    UnknownErrorNode,
    CallNode,
    TimeoutNode,
    CompletionProtocolNode,
    ScorchedEarthNode,
)


def test_simple_request():
    result = run(start_node=RNGNode())

    assert isinstance(result.answer, float)
    assert 0 < result.answer < 1


def test_fatal_error():
    i_node = FatalErrorNode()
    with pytest.raises(ExecutionException) as e:
        run(i_node)

    assert e.value.failed_request.source_id is None
    assert e.value.failed_request.sink_id == str(i_node.uuid)
    assert isinstance(e.value.final_exception, FatalException)
    assert e.value.exception_history == [e.value.final_exception]


def test_regular_error_without_completion():
    i_node = ScorchedEarthNode()

    with pytest.raises(ExecutionException) as exc:
        run(i_node, executor_config=ExecutorConfig(global_num_retries=6))

    err = exc.value
    print(err)

    assert err.failed_request.sink_id == str(i_node.uuid)
    assert isinstance(err.final_exception, GlobalRetriesExceeded)
    assert len(err.exception_history) == 6
    for error in err.exception_history:
        assert isinstance(error, ResetException)
        assert error.detail == REGULAR_ERROR
        assert error.node.uuid == i_node.uuid


def test_regular_error_with_completion():
    i_node = CompletionProtocolNode("Hello World")

    finished_result = run(i_node, executor_config=ExecutorConfig(global_num_retries=6))

    assert finished_result.answer == "Hello World"
    assert len(finished_result.exception_history) == 1


def test_unknown_error():
    i_node = UnknownErrorNode()

    with pytest.raises(Exception) as err:
        run(i_node)

    assert isinstance(err.value, Exception)


def test_override_scorched_earth():
    i_node = ScorchedEarthNode()

    with pytest.raises(ExecutionException) as err:
        run(
            i_node,
            executor_config=ExecutorConfig(
                global_num_retries=6, retry_upstream_request_on_failure=False
            ),
        )
    assert isinstance(err.value.final_exception, NodeException)
    assert err.value.failed_request.sink_id == str(i_node.uuid)
    assert len(err.value.exception_history) == 1


def test_call_with_fatal_error():
    i_node = CallNode(3, 3, FatalErrorNode)

    with pytest.raises(ExecutionException) as err:
        result = run(
            i_node,
        )

    assert isinstance(err.value.final_exception, NodeException)
    assert isinstance(err.value.final_exception.node, FatalErrorNode)
    assert isinstance(err.value.final_exception, FatalException)


def test_call_with_failed_retries():
    i_node = CallNode(3, 10, lambda: ScorchedEarthNode())

    with pytest.raises(ExecutionException) as err:
        result = run(
            i_node,
            executor_config=ExecutorConfig(global_num_retries=15, timeout=5),
        )

    assert isinstance(err.value.final_exception, GlobalRetriesExceeded)
    assert len(err.value.exception_history) >= 15
    # greater than 15 here cuz a couple of extra errors will come during the overall error handling (it is not important)
    for error in err.value.exception_history:
        assert isinstance(error, ResetException)


def test_call_with_inserted_data():
    i_node = CallNode(
        3,
        3,
        lambda: CompletionProtocolNode("Hello World"),
    )

    with pytest.raises(ExecutionException) as err:
        finished_run = run(i_node, executor_config=ExecutorConfig(global_num_retries=6))

    assert isinstance(err.value.final_exception, GlobalRetriesExceeded)
    assert len(err.value.exception_history) == 6


def test_crazy_errors():
    num_calls = 10
    parallel_calls = 5
    i_node = CallNode(
        num_calls,
        parallel_calls,
        lambda: CompletionProtocolNode("hello world"),
    )

    finished_result = run(
        i_node, executor_config=ExecutorConfig(global_num_retries=350, timeout=250)
    )

    assert isinstance(finished_result.answer, list)
    assert len(finished_result.answer) == num_calls * parallel_calls
    assert all([x == "hello world" for x in finished_result.answer])


def test_even_crazier_errors():
    i_node = CallNode(10, 50, lambda: RNGNode())

    finished_result = run(
        i_node,
        executor_config=ExecutorConfig(
            global_num_retries=10000, timeout=250, workers=290
        ),
    )

    assert isinstance(finished_result.answer, list)
    assert len(finished_result.answer) == 10 * 50
    assert all([0 <= x <= 1 for x in finished_result.answer])


def test_time_out():
    i_node = TimeoutNode(5)

    with pytest.raises(ExecutionException) as err:
        run(i_node, executor_config=ExecutorConfig(timeout=1))

    assert isinstance(err.value.final_exception, GlobalTimeOut)
    assert len(err.value.exception_history) == 0


def test_passed_time_out():
    i_node = TimeoutNode(1)

    finished_result = run(
        i_node, executor_config=ExecutorConfig(global_num_retries=10, timeout=10)
    )

    assert finished_result.answer is None


def test_complicated_graph_structure():
    i_node = CallNode(3, 5, lambda: TimeoutNode(1))

    try:
        run(i_node, executor_config=ExecutorConfig(timeout=5, global_num_retries=10000))
    except ExecutionException as err:
        assert isinstance(err.final_exception, GlobalTimeOut)


def test_complicated_graph_structure_2():
    i_node = CallNode(
        3,
        3,
        lambda: CompletionProtocolNode("Hello World"),
    )

    try:
        run(i_node, executor_config=ExecutorConfig(timeout=10, global_num_retries=10))
    except ExecutionException as err:
        assert isinstance(err.final_exception, GlobalRetriesExceeded)
