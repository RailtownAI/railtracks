import asyncio
from typing import Any
from unittest.mock import Mock, create_autospec, patch

import pytest
from railtracks.exceptions import GlobalTimeOutError
from railtracks.interaction._call import (
    _execute,
    _regular_message_filter,
    _run,
    _start,
    _top_level_message_filter,
    call,
)
from railtracks.nodes.nodes import Node
from railtracks.pubsub.messages import (
    FatalFailure,
    RequestCompletionMessage,
    RequestCreation,
    RequestFinishedBase,
)

from packages.railtracks.tests.unit_tests.execution.conftest import mock_node

# ============================ START Helper Classes ============================


class MockNode(Node):
    @classmethod
    def name(cls):
        return "Mock Node"

    def invoke(self):
        return ""

    @classmethod
    def type(cls):
        return "Agent"

    def __init__(self, value: Any):
        self.uuid = 123
        self.value = value

    async def run(self):
        return self.value


class MockRequestFinished(RequestFinishedBase):
    def __init__(self, request_id: str, result: Any = None):
        self.request_id = request_id
        self.result = result


class MockFatalFailure(FatalFailure):
    def __init__(self, error: str = "Fatal error"):
        self.error = error


# ============================ END Helper Classes ==============================


# ============================ START Message Filter Tests ============================


def test_regular_message_filter_matches_correct_request_id():
    """Test that regular message filter correctly identifies matching request IDs."""
    request_id = "test_request_123"
    filter_func = _regular_message_filter(request_id)

    # Test matching message
    matching_message = MockRequestFinished(request_id, "result")
    assert filter_func(matching_message) is True

    # Test non-matching message
    non_matching_message = MockRequestFinished("different_id", "result")
    assert filter_func(non_matching_message) is False

    # Test non-RequestFinishedBase message
    other_message = Mock(spec=RequestCompletionMessage)
    assert filter_func(other_message) is False


def test_top_level_message_filter_matches_request_id_and_fatal_failure():
    """Test that top-level message filter matches both request ID and fatal failures."""
    request_id = "test_request_123"
    filter_func = _top_level_message_filter(request_id)

    # Test matching request ID
    matching_message = MockRequestFinished(request_id, "result")
    assert filter_func(matching_message) is True

    # Test non-matching request ID
    non_matching_message = MockRequestFinished("different_id", "result")
    assert filter_func(non_matching_message) is False

    # Test fatal failure (should always match)
    fatal_failure = MockFatalFailure("Error occurred")
    assert filter_func(fatal_failure) is True

    # Test other message types
    other_message = Mock(spec=RequestCompletionMessage)
    assert filter_func(other_message) is False


# ============================ END Message Filter Tests ==============================


# ============================ START Call Function Tests ============================
@pytest.mark.asyncio
@patch(
    "railtracks.Session"
)  # generally not recommended, but we need this to counter the lazy import inside the call function
async def test_call_with_no_context_creates_runner(
    mock_session_class, mock_context_functions, mock_start
):
    """Test that call creates a Session when no context is present."""
    mock_node = MockNode

    # Setup mock session context manager
    session_instance = Mock()
    mock_session_class.return_value.__enter__.return_value = session_instance
    mock_session_class.return_value.__exit__.return_value = None

    mock_context_functions["is_context_present"].return_value = False
    mock_start.return_value = "test_result"

    result = await call(mock_node, "arg1", kwarg1="kwarg1")

    assert result == "test_result"
    mock_session_class.assert_called_once()
    mock_start.assert_called_once_with(
        mock_node, args=("arg1",), kwargs={"kwarg1": "kwarg1"}
    )


@pytest.mark.asyncio
async def test_call_with_inactive_context_calls_start(
    mock_context_functions, mock_start
):
    """Test that call uses _start when context is present but inactive."""
    mock_node = MockNode

    # Configure the context to simulate present but inactive
    mock_context_functions["is_context_present"].return_value = True
    mock_context_functions["is_context_active"].return_value = False
    mock_start.return_value = "test_result"

    result = await call(mock_node, "arg1", kwarg1="kwarg1")

    assert result == "test_result"
    mock_start.assert_called_once_with(
        mock_node, args=("arg1",), kwargs={"kwarg1": "kwarg1"}
    )


@pytest.mark.asyncio
async def test_call_with_active_context_calls_run(mock_context_functions, mock_run):
    """Test that call uses _run when context is active."""

    # Configure the context to simulate active context
    mock_context_functions["is_context_present"].return_value = True
    mock_context_functions["is_context_active"].return_value = True
    mock_run.return_value = "test_result"

    result = await call(MockNode, "arg1", kwarg1="kwarg1")

    assert result == "test_result"
    mock_run.assert_called_once_with(
        MockNode, args=("arg1",), kwargs={"kwarg1": "kwarg1"}
    )


@pytest.mark.asyncio
async def test_call_raises_type_error_with_function():
    """We are not supporting Callables as an argument to call. This is to make call a little ."""

    def test_function():
        return "function_result"
    
    with pytest.raises(TypeError):
        await call(test_function)

# ============================ END Call Function Tests ==============================


# ============================ START Start Function Tests ============================


@pytest.mark.asyncio
async def test_start_activates_and_shuts_down_publisher(
    full_context_setup, mock_execute
):
    """Test that _start properly activates and shuts down the publisher."""
    mock_node = MockNode
    mock_execute.return_value = "test_result"

    result = await _start(mock_node, args=("arg1",), kwargs={"kwarg1": "value1"})

    assert result == "test_result"
    full_context_setup["context"]["activate_publisher"].assert_called_once()
    full_context_setup["context"]["shutdown_publisher"].assert_called_once()


@pytest.mark.asyncio
async def test_start_handles_timeout_exception(full_context_setup, mock_execute):
    """Test that _start raises GlobalTimeOutError on timeout."""
    mock_node = MockNode

    async def slow_execute(*args, **kwargs):
        await asyncio.sleep(1)  # Simulate slow operation
        return "result"

    mock_execute.side_effect = slow_execute

    with pytest.raises(GlobalTimeOutError) as exc_info:
        await _start(mock_node, args=(), kwargs={})

    assert exc_info.value.timeout == 0.01
    full_context_setup["context"]["shutdown_publisher"].assert_called_once()


@pytest.mark.asyncio
async def test_start_preserves_internal_timeout_error(full_context_setup, mock_execute):
    """Test that _start preserves timeout errors from the coroutine itself."""
    mock_node = MockNode

    async def timeout_execute(*args, **kwargs):
        raise asyncio.TimeoutError("Internal timeout")

    mock_execute.side_effect = timeout_execute

    with pytest.raises(asyncio.TimeoutError) as exc_info:
        await _start(mock_node, args=(), kwargs={})

    assert str(exc_info.value) == "Internal timeout"
    full_context_setup["context"]["shutdown_publisher"].assert_called_once()


# ============================ END Start Function Tests ==============================


# ============================ START Run Function Tests ============================


@pytest.mark.asyncio
async def test_run_calls_execute_with_regular_filter(mock_execute):
    """Test that _run calls _execute with the regular message filter."""
    mock_node = MockNode
    mock_execute.return_value = "test_result"

    result = await _run(mock_node, ("arg1",), {"kwarg1": "value1"})

    assert result == "test_result"
    mock_execute.assert_called_once()

    # Verify the correct arguments were passed
    call_args = mock_execute.call_args
    assert call_args[0][0] == mock_node
    assert call_args[1]["args"] == ("arg1",)
    assert call_args[1]["kwargs"] == {"kwarg1": "value1"}
    # message_filter should be _regular_message_filter
    assert callable(call_args[1]["message_filter"])


# ============================ END Run Function Tests ==============================


# ============================ START Execute Function Tests ============================


@pytest.mark.asyncio
async def test_execute_publishes_request_and_waits_for_response(full_context_setup):
    """Test that _execute publishes a request and waits for the response."""
    mock_node = MockNode

    # Mock the listener to return the expected result
    future_result = asyncio.Future()
    future_result.set_result("execution_result")
    full_context_setup["publisher"].listener.return_value = future_result

    message_filter = _regular_message_filter
    result = await _execute(mock_node, ("arg1",), {"kwarg1": "value1"}, message_filter)

    assert result._result == "execution_result"

    # Verify publisher.publish was called with correct RequestCreation
    full_context_setup["publisher"].publish.assert_called_once()
    published_message = full_context_setup["publisher"].publish.call_args[0][0]
    assert isinstance(published_message, RequestCreation)
    assert published_message.current_node_id == "parent_123"
    assert published_message.running_mode == "async"
    assert published_message.new_node_type == mock_node
    assert published_message.args == ("arg1",)
    assert published_message.kwargs == {"kwarg1": "value1"}

    # Verify listener was set up correctly
    full_context_setup["publisher"].listener.assert_called_once()


# ============================ END Execute Function Tests ==============================


# ============================ START Edge Case Tests ============================
@pytest.mark.asyncio
async def test_call_with_none_arguments(mock_run):
    """Test call with None as arguments."""
    mock_node = MockNode
    mock_run.return_value = "none_result"
    result = await mock_run(mock_node, None, test_arg=None)

    assert result == "none_result"
    mock_run.assert_called_once_with(mock_node, None, test_arg=None)


@pytest.mark.asyncio
async def test_call_with_empty_arguments(mock_run):
    """Test call with no arguments."""
    mock_node = MockNode
    mock_run.return_value = "empty_result"
    result = await mock_run(mock_node)
    assert result == "empty_result"
    mock_run.assert_called_once_with(mock_node)


# ============================ END Edge Case Tests ==============================
