import asyncio
import pytest
from unittest.mock import Mock, AsyncMock, patch
from typing import Any
from requestcompletion.interaction.call import (
    call,
    call_sync,
    _start,
    _run,
    _execute,
    _regular_message_filter,
    _top_level_message_filter,
)
from requestcompletion.nodes.nodes import Node
from requestcompletion.exceptions import GlobalTimeOutError
from requestcompletion.pubsub.messages import (
    RequestCompletionMessage,
    RequestFinishedBase,
    FatalFailure,
    RequestCreation,
)

# ============================ START Helper Classes ============================

class MockNode(Node):
    @classmethod
    def pretty_name(cls):
        return "Mock Node"
    
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
async def test_call_with_no_context_creates_runner(mock_context_functions, mock_runner, mock_start):
    """Test that call creates a Runner when no context is present."""
    mock_node = Mock(return_value=MockNode("test_result"))
    
    # Configure the context to simulate no context present
    mock_context_functions['is_context_present'].return_value = False
    mock_start.return_value = "test_result"
    
    result = await call(mock_node, "arg1", kwarg1="kwarg1")
    
    assert result == "test_result"
    mock_runner.assert_called_once()
    mock_start.assert_called_once_with(mock_node, args=("arg1",), kwargs={"kwarg1": "kwarg1"})


@pytest.mark.asyncio
async def test_call_with_inactive_context_calls_start(mock_context_functions, mock_start):
    """Test that call uses _start when context is present but inactive."""
    mock_node = Mock(return_value=MockNode("test_result"))
    
    # Configure the context to simulate present but inactive
    mock_context_functions['is_context_present'].return_value = True
    mock_context_functions['is_context_active'].return_value = False
    mock_start.return_value = "test_result"
    
    result = await call(mock_node, "arg1", kwarg1="kwarg1")
    
    assert result == "test_result"
    mock_start.assert_called_once_with(mock_node, args=("arg1",), kwargs={"kwarg1": "kwarg1"})


@pytest.mark.asyncio
async def test_call_with_active_context_calls_run(mock_context_functions, mock_run):
    """Test that call uses _run when context is active."""
    mock_node = Mock(return_value=MockNode("test_result"))
    
    # Configure the context to simulate active context
    mock_context_functions['is_context_present'].return_value = True
    mock_context_functions['is_context_active'].return_value = True
    mock_run.return_value = "test_result"
    
    result = await call(mock_node, "arg1", kwarg1="kwarg1")
    
    assert result == "test_result"
    mock_run.assert_called_once_with(mock_node, args=("arg1",), kwargs={"kwarg1": "kwarg1"})


@pytest.mark.asyncio
async def test_call_converts_function_to_node_behaviorally_with_side_effect():
    """  No good was of testing if the function was made into a node, i tried using mock but ran into a circular import error"""
    called = False
    def test_function():
        nonlocal called
        called = True
        return "function_result"

    result = await call(test_function)

    assert result == "function_result"
    assert called is True

# ============================ END Call Function Tests ==============================


# ============================ START Start Function Tests ============================

@pytest.mark.asyncio
async def test_start_activates_and_shuts_down_publisher(full_context_setup, mock_execute):
    """Test that _start properly activates and shuts down the publisher."""
    mock_node = Mock(return_value=MockNode("test_result"))
    mock_execute.return_value = "test_result"
    
    result = await _start(mock_node, args=("arg1",), kwargs={"kwarg1": "value1"})
    
    assert result == "test_result"
    full_context_setup['context']['activate_publisher'].assert_called_once()
    full_context_setup['context']['shutdown_publisher'].assert_called_once()


@pytest.mark.asyncio
async def test_start_handles_timeout_exception(full_context_setup, mock_execute):
    """Test that _start raises GlobalTimeOutError on timeout."""
    mock_node = Mock(return_value=MockNode("test_result"))
    
    async def slow_execute(*args, **kwargs):
        await asyncio.sleep(1)  # Simulate slow operation
        return "result"
    
    mock_execute.side_effect = slow_execute
    
    with pytest.raises(GlobalTimeOutError) as exc_info:
        await _start(mock_node, args=(), kwargs={})
    
    assert exc_info.value.timeout == 0.01
    full_context_setup['context']['shutdown_publisher'].assert_called_once()


@pytest.mark.asyncio
async def test_start_preserves_internal_timeout_error(full_context_setup, mock_execute):
    """Test that _start preserves timeout errors from the coroutine itself."""
    mock_node = Mock(return_value=MockNode("test_result"))
    
    async def timeout_execute(*args, **kwargs):
        raise asyncio.TimeoutError("Internal timeout")
    
    mock_execute.side_effect = timeout_execute
    
    with pytest.raises(asyncio.TimeoutError) as exc_info:
        await _start(mock_node, args=(), kwargs={})
    
    assert str(exc_info.value) == "Internal timeout"
    full_context_setup['context']['shutdown_publisher'].assert_called_once()

# ============================ END Start Function Tests ==============================


# ============================ START Run Function Tests ============================

@pytest.mark.asyncio
async def test_run_calls_execute_with_regular_filter(mock_execute):
    """Test that _run calls _execute with the regular message filter."""
    mock_node = Mock(return_value=MockNode("test_result"))
    mock_execute.return_value = "test_result"
    
    result = await _run(mock_node, ("arg1",), {"kwarg1": "value1"})
    
    assert result == "test_result"
    mock_execute.assert_called_once()
    
    # Verify the correct arguments were passed
    call_args = mock_execute.call_args
    assert call_args[0][0] == mock_node
    assert call_args[1]['args'] == ("arg1",)
    assert call_args[1]['kwargs'] == {"kwarg1": "value1"}
    # message_filter should be _regular_message_filter
    assert callable(call_args[1]['message_filter'])

# ============================ END Run Function Tests ==============================


# ============================ START Execute Function Tests ============================

@pytest.mark.asyncio
async def test_execute_publishes_request_and_waits_for_response(full_context_setup):
    """Test that _execute publishes a request and waits for the response."""
    mock_node = Mock(return_value=MockNode("test_result"))
    
    # Mock the listener to return the expected result
    future_result = asyncio.Future()
    future_result.set_result("execution_result")
    full_context_setup['publisher'].listener.return_value = future_result
    
    message_filter = _regular_message_filter
    result = await _execute(mock_node, ("arg1",), {"kwarg1": "value1"}, message_filter)
    
    assert result._result == "execution_result"
    
    # Verify publisher.publish was called with correct RequestCreation
    full_context_setup['publisher'].publish.assert_called_once()
    published_message = full_context_setup['publisher'].publish.call_args[0][0]
    assert isinstance(published_message, RequestCreation)
    assert published_message.current_node_id == "parent_123"
    assert published_message.running_mode == "async"
    assert published_message.new_node_type == mock_node
    assert published_message.args == ("arg1",)
    assert published_message.kwargs == {"kwarg1": "value1"}
    
    # Verify listener was set up correctly
    full_context_setup['publisher'].listener.assert_called_once()

# ============================ END Execute Function Tests ==============================


# ============================ START Call Sync Tests ============================
def test_call_sync_with_no_running_loop():
    """Test call_sync when no event loop is running."""
    mock_node = Mock(return_value=MockNode("sync_result"))
    
    with patch('asyncio.get_running_loop', side_effect=RuntimeError("No running loop")), \
         patch('asyncio.new_event_loop') as mock_new_loop, \
         patch('asyncio.set_event_loop') as mock_set_loop, \
         patch('requestcompletion.interaction.call.call') as mock_call:
        
        mock_loop = Mock()
        mock_task = Mock()
        mock_new_loop.return_value = mock_loop
        mock_loop.create_task.return_value = mock_task
        mock_loop.run_until_complete.return_value = "sync_result"
        
        future = Mock()
        future.set_result = Mock()
        mock_call.return_value = future
        
        result = call_sync(mock_node, "arg1", kwarg1="value1")
        
        assert result == "sync_result"
        mock_new_loop.assert_called_once()
        mock_set_loop.assert_called_once_with(mock_loop)
        mock_loop.create_task.assert_called_once()
        mock_loop.run_until_complete.assert_called_once_with(mock_task)
        mock_loop.close.assert_called_once()

def test_call_sync_with_running_loop_raises_error():
    """Test that call_sync raises RuntimeError when called from within a running loop."""
    mock_node = Mock(return_value=MockNode("sync_result"))
    mock_loop = Mock()
    
    with patch('asyncio.get_running_loop', return_value=mock_loop):
        with pytest.raises(RuntimeError) as exc_info:
            call_sync(mock_node, "arg1")
        
        assert "cannot call `call_sync` from within an already running event loop" in str(exc_info.value)
        assert "Use `call` instead" in str(exc_info.value)

# ============================ END Call Sync Tests ==============================

# ============================ START Edge Case Tests ============================
@pytest.mark.asyncio
async def test_call_with_none_arguments(mock_run):
    """Test call with None as arguments."""
    mock_node = Mock(return_value=MockNode("none_result"))
    mock_run.return_value = "none_result"
    result = await mock_run(mock_node, None, test_arg=None)
    
    assert result == "none_result"
    mock_run.assert_called_once_with(mock_node, None, test_arg=None)


@pytest.mark.asyncio
async def test_call_with_empty_arguments(mock_run):
    """Test call with no arguments."""
    mock_node = Mock(return_value=MockNode("empty_result"))
    mock_run.return_value = "empty_result"
    result = await mock_run(mock_node)
    assert result == "empty_result"
    mock_run.assert_called_once_with(mock_node)


def test_call_sync_loop_cleanup_on_exception():
    """Test that call_sync properly cleans up the event loop even if an exception occurs."""
    mock_node = Mock(return_value=MockNode("exception_result"))
    
    with patch('asyncio.get_running_loop', side_effect=RuntimeError("No running loop")), \
         patch('asyncio.new_event_loop') as mock_new_loop, \
         patch('asyncio.set_event_loop') as mock_set_loop:
        
        mock_loop = Mock()
        mock_new_loop.return_value = mock_loop
        mock_loop.create_task.side_effect = Exception("Task creation failed")
        
        with pytest.raises(Exception) as exc_info:
            call_sync(mock_node)
        
        assert str(exc_info.value) == "Task creation failed"
        mock_loop.close.assert_called_once()  # Ensure cleanup happened

# ============================ END Edge Case Tests ==============================