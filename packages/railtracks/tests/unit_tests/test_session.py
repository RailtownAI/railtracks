import json
from pathlib import Path

import pytest
from unittest.mock import MagicMock, patch, call, PropertyMock, Mock
import asyncio
import railtracks as rt
from railtracks import Session, session

# ================= START Mock Fixture ============
@pytest.fixture
def mock_dependencies(monkeypatch):
    m_mark_session_logging_override = MagicMock()
    m_restore_module_logging = MagicMock()
    m_get_global_config = MagicMock()
    m_RTPublisher = MagicMock()
    m_ExecutionInfo = MagicMock(create_new=MagicMock())
    m_Coordinator = MagicMock()
    m_RTState = MagicMock()
    m_register_globals = MagicMock()
    m_delete_globals = MagicMock()

    monkeypatch.setattr('railtracks._session.mark_session_logging_override', m_mark_session_logging_override)
    monkeypatch.setattr('railtracks._session.restore_module_logging', m_restore_module_logging)
    monkeypatch.setattr('railtracks._session.get_global_config', m_get_global_config)
    monkeypatch.setattr('railtracks._session.RTPublisher', m_RTPublisher)
    monkeypatch.setattr('railtracks._session.ExecutionInfo', m_ExecutionInfo)
    monkeypatch.setattr('railtracks._session.Coordinator', m_Coordinator)
    monkeypatch.setattr('railtracks._session.RTState', m_RTState)
    monkeypatch.setattr('railtracks._session.register_globals', m_register_globals)
    monkeypatch.setattr('railtracks._session.delete_globals', m_delete_globals)

    return {
        'mark_session_logging_override': m_mark_session_logging_override,
        'restore_module_logging': m_restore_module_logging,
        'get_global_config': m_get_global_config,
        'RTPublisher': m_RTPublisher,
        'ExecutionInfo': m_ExecutionInfo,
        'Coordinator': m_Coordinator,
        'RTState': m_RTState,
        'register_globals': m_register_globals,
        'delete_globals': m_delete_globals,
    }
# ================ END Mock Fixture ===============

# ================= START Session: Construction & Context Manager ============
def test_runner_construction_with_explicit_config_and_context(mock_dependencies):
    context = {'foo': 'bar'}
    # Setup mocks with needed API
    pub_mock = mock_dependencies['RTPublisher'].return_value
    state_mock = mock_dependencies['RTState'].return_value
    info_mock = MagicMock()
    state_mock.info = info_mock

    # Should not raise
    r = Session(context=context)
    assert hasattr(r, 'publisher')
    assert hasattr(r, 'rt_state')
    assert hasattr(r, 'coordinator')
    assert r.rt_state.info == info_mock

def test_runner_construction_with_defaults(mock_dependencies):
    # Should call get_global_config()
    Session()
    assert mock_dependencies['get_global_config'].called

def test_runner_context_manager_closes_on_exit(mock_dependencies):

    context = {}
    runner = Session(context=context)
    with patch.object(runner, "_close") as mock_close:
        with runner:
            pass
        mock_close.assert_called_once()

# ================ END Session: Construction & Context Manager ===============


# ================= START Session: Singleton/Instance Id Behavior ============

def test_session_name_is_taken_from_executor_config():
    name = "abc123"

    r = Session(name=name)
    assert r.name == name

# ================ END Session: Singleton/Instance Id Behavior ===============


# ================= START Session: Logging Override Tests ===============

def test_session_with_logging_setting_marks_override(mock_dependencies):
    """Test that Session with logging_setting marks session logging override."""
    runner = Session(logging_setting="VERBOSE")
    assert mock_dependencies['mark_session_logging_override'].called
    assert runner._has_custom_logging is True

def test_session_with_log_file_marks_override(mock_dependencies):
    """Test that Session with log_file marks session logging override."""
    runner = Session(log_file="/tmp/test.log")
    assert mock_dependencies['mark_session_logging_override'].called
    assert runner._has_custom_logging is True

def test_session_with_both_logging_params_marks_override(mock_dependencies):
    """Test that Session with both logging params marks session logging override."""
    runner = Session(logging_setting="QUIET", log_file="/tmp/test.log")
    assert mock_dependencies['mark_session_logging_override'].called
    assert runner._has_custom_logging is True

def test_session_without_logging_params_no_override(mock_dependencies):
    """Test that Session without logging params does not mark override."""
    runner = Session()
    assert not mock_dependencies['mark_session_logging_override'].called
    assert runner._has_custom_logging is False

# ================ END Session: Logging Override Tests ===============


# ================= START Session: setup_subscriber ===============

def test_setup_subscriber_adds_subscriber_if_present():
    sub_subscriber = Mock()
    runner = Session(broadcast_callback=sub_subscriber)
    runner.publisher = MagicMock()
    with patch('railtracks._session.stream_subscriber', return_value="fake_stream_sub") as m_stream:
        runner._setup_subscriber()
        runner.publisher.subscribe.assert_called_once_with(
            "fake_stream_sub", name="Streaming Subscriber"
        )
        m_stream.assert_called_once_with(sub_subscriber)

def test_setup_subscriber_noop_if_no_subscriber(mock_dependencies):
    runner = Session()
    runner.executor_config.subscriber = None
    runner.publisher = MagicMock()
    with patch('railtracks._session.stream_subscriber') as m_stream:
        runner._setup_subscriber()
        runner.publisher.subscribe.assert_not_called()
        m_stream.assert_not_called()

# ================ END Session: setup_subscriber ===============


# ================= START Session: _close & __exit__ ===============

def test_close_calls_shutdown_and_delete(mock_dependencies):
    """Test that _close calls shutdown and delete_globals."""
    runner = Session()
    runner.rt_state = MagicMock()
    runner._close()
    assert runner.rt_state.shutdown.called
    assert mock_dependencies['delete_globals'].called

def test_close_restores_logging_when_custom_logging_used(mock_dependencies):
    """Test that _close calls restore_module_logging when custom logging was used."""
    runner = Session(logging_setting="VERBOSE")
    runner.rt_state = MagicMock()
    runner._close()
    assert mock_dependencies['restore_module_logging'].called

def test_close_does_not_restore_logging_when_no_custom_logging(mock_dependencies):
    """Test that _close does not call restore_module_logging when no custom logging."""
    runner = Session()
    runner.rt_state = MagicMock()
    runner._close()
    assert not mock_dependencies['restore_module_logging'].called

# ================ END Session: _close & __exit__ ===============


# ================= START Session: info property ===============

def test_info_property_returns_rt_state_info(mock_dependencies):
    runner = Session()
    rt_info = MagicMock()
    runner.rt_state.info = rt_info
    assert runner.info is rt_info

# ================ END Session: info property ===============


# ================= START Session: Check saved data ===============
def test_session_saves_data():
    name = "abs53562j12h267"

    serialization_mock = {"Key": "Value"}
    info = MagicMock()
    info.graph_serialization.return_value = serialization_mock


    with patch.object(Session, 'info', new_callable=PropertyMock) as mock_runner:
        mock_runner.return_value.graph_serialization.return_value = serialization_mock

        r = Session(
            name=name,
            save_state=True,
        )
        r.__exit__(None, None, None)


    path = Path(".railtracks/data/sessions") / f"{r.name}_{r._identifier}.json"
    data = json.loads(path.read_text())
    assert data["runs"] == serialization_mock
    assert "session_id" in data
    assert data["session_name"] == name


def test_session_not_saves_data():
    config = MagicMock()

    run_id = "Run 2"
    config.run_identifier = run_id
    config.save_state = False

    serialization_mock = '{"Key": "Value"}'
    info = MagicMock()
    info.graph_serialization.return_value = serialization_mock

    with patch.object(Session, 'info', new_callable=PropertyMock) as mock_runner:
        mock_runner.return_value.graph_serialization.return_value = serialization_mock

        r = Session(name=run_id, save_state=False)
        r.__exit__(None, None, None)




    path = Path(".railtracks/data/sessions") / f"{run_id}.json"
    assert not path.is_file()


def test_session_fallback_on_invalid_name():
    """Test that session falls back to identifier-only filename when name causes issues."""
    # Use a name that would cause issues in file path creation
    invalid_name = "test/invalid:name*with|bad<chars>"

    serialization_mock = {"Key": "Value"}

    with patch.object(Session, 'info', new_callable=PropertyMock) as mock_runner:
        mock_runner.return_value.graph_serialization.return_value = serialization_mock

        # Mock Path.touch to raise an exception when the path contains the invalid name in the filename
        original_touch = Path.touch
        def mock_touch(self, *args, **kwargs):
            # Only raise exception if the invalid name is in the filename part (not just any path)
            if invalid_name in self.name:
                raise OSError("Invalid characters in filename")
            return original_touch(self, *args, **kwargs)

        with patch.object(Path, 'touch', mock_touch), \
             patch('railtracks._session.logger') as mock_logger:

            r = Session(name=invalid_name, save_state=True)
            r.__exit__(None, None, None)

            # Verify that a warning was logged about the invalid name
            mock_logger.warning.assert_called()
            warning_calls = [call[0][0] for call in mock_logger.warning.call_args_list]
            fallback_warning = None
            for call in warning_calls:
                if "falling back to using the unique identifier only" in call:
                    fallback_warning = call
                    break

            assert fallback_warning is not None, "Expected fallback warning not found"
            assert invalid_name in fallback_warning

            # Verify that the fallback file was created (identifier only)
            fallback_path = Path(".railtracks/data/sessions") / f"{r._identifier}.json"
            assert fallback_path.exists()

            # Clean up
            if fallback_path.exists():
                fallback_path.unlink()


# ================= START Session: Decorator Tests ===============

def test_session_decorator_creates_function():
    """Test that the session decorator returns a decorator function."""
    decorator = session()
    assert callable(decorator)

def test_session_decorator_with_parameters():
    """Test session decorator with various parameters."""
    decorator = session(
        timeout=30,
        context={"test": "value"},
        end_on_error=True,
        logging_setting="VERBOSE"
    )
    assert callable(decorator)

@pytest.mark.asyncio
async def test_session_decorator_wraps_async_function(mock_dependencies):
    """Test that the decorator properly wraps an async function and returns tuple."""
    @session(timeout=10)
    async def test_function():
        return "test_result"

    result, session_obj = await test_function()
    assert result == "test_result"
    assert isinstance(session_obj, Session)

@pytest.mark.asyncio
async def test_session_decorator_with_function_args(mock_dependencies):
    """Test that the decorator preserves function arguments and returns tuple."""
    @session()
    async def test_function(arg1, arg2, kwarg1=None):
        return f"{arg1}-{arg2}-{kwarg1}"

    result, session_obj = await test_function("a", "b", kwarg1="c")
    assert result == "a-b-c"
    assert isinstance(session_obj, Session)

@pytest.mark.asyncio
async def test_session_decorator_context_manager_behavior(mock_dependencies):
    """Test that the decorator properly manages session lifecycle."""
    session_created = False
    session_closed = False

    original_init = Session.__init__
    original_exit = Session.__exit__

    def mock_init(self, *args, **kwargs):
        nonlocal session_created
        session_created = True
        return original_init(self, *args, **kwargs)

    def mock_exit(self, *args, **kwargs):
        nonlocal session_closed
        session_closed = True
        return original_exit(self, *args, **kwargs)

    with patch.object(Session, '__init__', mock_init), \
         patch.object(Session, '__exit__', mock_exit):

        @session()
        async def test_function():
            return "done"

        result, session_obj = await test_function()
        assert result == "done"
        assert isinstance(session_obj, Session)

    assert session_created
    assert session_closed

def test_session_decorator_raises_error_on_sync_function():
    """Test that the session decorator raises TypeError when applied to sync function."""
    with pytest.raises(TypeError, match="@session decorator can only be applied to async functions"):
        @session()
        def sync_function():
            return "this should fail"

def test_session_decorator_error_message_contains_function_name():
    """Test that the error message includes the function name."""
    with pytest.raises(TypeError, match="Function 'my_sync_func' is not async"):
        @session()
        def my_sync_func():
            return "this should fail"

def test_rt_session_decorator_raises_error_on_sync_function():
    """Test that rt.session also raises TypeError when applied to sync function."""
    with pytest.raises(TypeError, match="@session decorator can only be applied to async functions"):
        @session()
        def sync_function():
            return "this should fail"

@pytest.mark.asyncio
async def test_session_decorator_returns_session_object(mock_dependencies):
    """Test that decorator returns both result and session object with access to session info."""
    @session(name="test-session-123")
    async def test_function():
        return "test_result"

    result, session_obj = await test_function()

    # Verify we get both the result and session
    assert result == "test_result"
    assert isinstance(session_obj, Session)
    assert session_obj.name == "test-session-123"

    # Verify we can access session properties
    assert hasattr(session_obj, 'info')
    assert hasattr(session_obj, 'payload')

@pytest.mark.asyncio
async def test_session_decorator_handles_tuple_returns(mock_dependencies):
    """Test that decorator properly handles functions that return tuples."""
    @session()
    async def function_returning_tuple():
        return "hello", 42, True

    result, session_obj = await function_returning_tuple()

    # The result should be the tuple returned by the function
    assert result == ("hello", 42, True)
    assert isinstance(session_obj, Session)

    # The tuple structure is preserved
    val1, val2, val3 = result
    assert val1 == "hello"
    assert val2 == 42
    assert val3 == True

# ================ END Session: Decorator Tests ===============


# ================= START Session: _construct_agent_data Tests ===============

def test_construct_agent_data_with_save_data_false(mock_dependencies):
    """Test that _construct_agent_data is not called when save_data is False."""
    runner = Session(save_data=False)
    runner.rt_state.info = MagicMock()
    
    # When save_data is False, _construct_agent_data should not be called
    # This is tested in __exit__ flow, so we skip this test scenario

def test_construct_agent_data_with_save_data_true(mock_dependencies):
    """Test _construct_agent_data with save_data=True (includes all data)."""
    from railtracks.built_nodes.concrete.response import LLMResponse
    from railtracks.llm.message import UserMessage, AssistantMessage, Role
    
    runner = Session(save_data=True)
    
    # Mock request template
    mock_request = MagicMock()
    mock_request.input = (("arg1", "arg2"), {"key": "value"})
    
    # Mock LLM response
    mock_message_history = [
        UserMessage("Hello"),
        AssistantMessage("Hi there"),
    ]
    mock_response = LLMResponse(content="Test output", message_history=mock_message_history)
    
    # Mock run info
    mock_run = {"name": "TestAgent", "run_id": "test-123", "nodes": []}
    
    # Setup info mock
    runner.rt_state.info.insertion_requests = [mock_request]
    runner.rt_state.info.answer = [mock_response]
    runner.rt_state.info.graph_serialization = MagicMock(return_value=[mock_run])
    
    with patch.object(runner, '_save_agent_data', return_value=Path("/tmp/test.json")):
        with patch('builtins.open', create=True) as mock_open:
            mock_file = MagicMock()
            mock_open.return_value.__enter__.return_value = mock_file
            with patch('json.dump') as mock_json_dump:
                runner._construct_agent_data()
                
                # Verify json.dump was called
                assert mock_json_dump.called
                
                # Verify the data structure has agent_internals with data
                call_args = mock_json_dump.call_args[0][0]
                assert len(call_args) == 1
                data_point = call_args[0]
                assert data_point["agent_internals"] is not None
                assert "run_id" in data_point["agent_internals"]

def test_construct_agent_data_with_full_data(mock_dependencies):
    """Test _construct_agent_data includes internals, message_history, and tool invocations."""
    from railtracks.built_nodes.concrete.response import LLMResponse
    from railtracks.llm.message import UserMessage, AssistantMessage
    from railtracks.llm.content import ToolCall, ToolResponse
    
    runner = Session(save_data=True)
    
    # Mock request template
    mock_request = MagicMock()
    mock_request.input = (("arg1",), {"kwarg1": "value1"})
    
    # Mock tool invocations
    mock_tool_call = MagicMock()
    mock_tool_call.name = "test_tool"
    mock_tool_call.arguments = {"param": "value"}
    
    mock_tool_response = MagicMock()
    mock_tool_response.result = "tool result"
    
    # Mock LLM response with tool invocations
    mock_message_history = [
        UserMessage("Use a tool"),
        AssistantMessage("Using tool"),
    ]
    mock_response = LLMResponse(content="Final output", message_history=mock_message_history)
    mock_response._tool_invocations = [(mock_tool_call, mock_tool_response)]
    
    # Mock run info
    mock_run = {"name": "FullAgent", "run_id": "full-456", "nodes": []}
    
    # Setup info mock
    runner.rt_state.info.insertion_requests = [mock_request]
    runner.rt_state.info.answer = [mock_response]
    runner.rt_state.info.graph_serialization = MagicMock(return_value=[mock_run])
    
    with patch.object(runner, '_save_agent_data', return_value=Path("/tmp/test_full.json")):
        with patch('builtins.open', create=True) as mock_open:
            mock_file = MagicMock()
            mock_open.return_value.__enter__.return_value = mock_file
            with patch('json.dump') as mock_json_dump:
                runner._construct_agent_data()
                
                # Verify json.dump was called
                assert mock_json_dump.called
                
                # Verify the data structure includes internals
                call_args = mock_json_dump.call_args[0][0]
                assert len(call_args) == 1
                data_point = call_args[0]
                assert "agent_internals" in data_point
                assert data_point["agent_internals"] is not None
                assert "message_history" in data_point["agent_internals"]
                assert "tool_invocations" in data_point["agent_internals"]

def test_construct_agent_data_serializes_messages_correctly(mock_dependencies):
    """Test that message history is properly serialized to JSON-compatible format."""
    from railtracks.built_nodes.concrete.response import LLMResponse
    from railtracks.llm.message import UserMessage, AssistantMessage, SystemMessage
    
    runner = Session(save_data=True)
    
    # Mock request template
    mock_request = MagicMock()
    mock_request.input = ((), {})
    
    # Create actual message objects
    mock_message_history = [
        UserMessage("User question"),
        AssistantMessage("Assistant response"),
        SystemMessage("System prompt"),
    ]
    
    mock_response = LLMResponse(content="Output", message_history=mock_message_history)
    mock_response._tool_invocations = []
    
    mock_run = {"name": "MessageTestAgent", "run_id": "msg-789", "nodes": []}
    
    runner.rt_state.info.insertion_requests = [mock_request]
    runner.rt_state.info.answer = [mock_response]
    runner.rt_state.info.graph_serialization = MagicMock(return_value=[mock_run])
    
    with patch.object(runner, '_save_agent_data', return_value=Path("/tmp/test_msg.json")):
        with patch('builtins.open', create=True):
            with patch('json.dump') as mock_json_dump:
                runner._construct_agent_data()
                
                # Get the dumped data
                call_args = mock_json_dump.call_args[0][0]
                data_point = call_args[0]
                
                # Verify message_history is serialized as list of dicts
                msg_history = data_point["agent_internals"]["message_history"]
                assert isinstance(msg_history, list)
                assert len(msg_history) == 3
                assert all(isinstance(msg, dict) for msg in msg_history)
                assert all("role" in msg and "content" in msg for msg in msg_history)

def test_construct_agent_data_with_non_llm_response(mock_dependencies):
    """Test _construct_agent_data handles non-LLMResponse answers."""
    runner = Session(save_data=True)
    
    # Mock request template
    mock_request = MagicMock()
    mock_request.input = (("simple",), {})
    
    # Non-LLM response (just a string)
    simple_answer = "Simple string output"
    
    mock_run = {"name": "SimpleAgent", "run_id": "simple-999", "nodes": []}
    
    runner.rt_state.info.insertion_requests = [mock_request]
    runner.rt_state.info.answer = [simple_answer]
    runner.rt_state.info.graph_serialization = MagicMock(return_value=[mock_run])
    
    with patch.object(runner, '_save_agent_data', return_value=Path("/tmp/test_simple.json")):
        with patch('builtins.open', create=True):
            with patch('json.dump') as mock_json_dump:
                runner._construct_agent_data()
                
                # Verify data was saved with agent_internals containing run_id
                call_args = mock_json_dump.call_args[0][0]
                data_point = call_args[0]
                assert data_point["agent_output"] == simple_answer
                assert "run_id" in data_point["agent_internals"]

def test_construct_agent_data_handles_save_failure(mock_dependencies):
    """Test _construct_agent_data handles file save failures gracefully."""
    from railtracks.built_nodes.concrete.response import LLMResponse
    from railtracks.llm.message import UserMessage
    
    runner = Session(save_data=True)
    
    mock_request = MagicMock()
    mock_request.input = ((), {})
    
    mock_response = LLMResponse(content="Output", message_history=[UserMessage("Test")])
    mock_run = {"name": "FailAgent", "run_id": "fail-111", "nodes": []}
    
    runner.rt_state.info.insertion_requests = [mock_request]
    runner.rt_state.info.answer = [mock_response]
    runner.rt_state.info.graph_serialization = MagicMock(return_value=[mock_run])
    
    # Mock _save_agent_data to return None (failure case)
    with patch.object(runner, '_save_agent_data', return_value=None):
        with patch('railtracks._session.logger') as mock_logger:
            runner._construct_agent_data()
            
            # Verify warning was logged
            mock_logger.warning.assert_called_once()
            assert "Could not save agent data" in str(mock_logger.warning.call_args)

# ================ END Session: _construct_agent_data Tests ===============


# ================= START Session: _save_agent_data Tests ===============

def test_save_agent_data_with_session_name(mock_dependencies):
    """Test _save_agent_data creates file with session name."""
    runner = Session(name="test_session")
    
    result = runner._save_agent_data("test_session")
    
    assert result is not None
    assert isinstance(result, Path)
    assert "test_session" in result.name
    assert runner._identifier in result.name
    assert result.parent.name == "agent_data"
    
    # Cleanup
    if result.exists():
        result.unlink()

def test_save_agent_data_without_session_name(mock_dependencies):
    """Test _save_agent_data creates file with identifier only when no name."""
    runner = Session(name=None)
    
    result = runner._save_agent_data("")
    
    assert result is not None
    assert isinstance(result, Path)
    assert result.name == f"{runner._identifier}.json"
    assert result.parent.name == "agent_data"
    
    # Cleanup
    if result.exists():
        result.unlink()

def test_save_agent_data_creates_directory(mock_dependencies):
    """Test _save_agent_data creates directory if it doesn't exist."""
    import tempfile
    import shutil
    
    # Use a temporary directory
    with tempfile.TemporaryDirectory() as tmpdir:
        runner = Session(name="dir_test")
        
        # Mock the railtracks_dir to use temp directory
        with patch('railtracks._session.Path') as mock_path:
            temp_path = Path(tmpdir) / ".railtracks" / "data" / "agent_data"
            mock_path.return_value = temp_path
            
            # The actual implementation creates the directory
            result = runner._save_agent_data("dir_test")
            
            # Directory should be created by mkdir call
            assert result is not None

def test_save_agent_data_handles_invalid_filename(mock_dependencies):
    """Test _save_agent_data handles invalid filenames gracefully."""
    # Use invalid characters in name
    invalid_name = "test/invalid:name*"
    runner = Session(name=invalid_name)
    
    with patch('railtracks._session.logger') as mock_logger:
        # Mock Path.touch to raise an exception
        with patch.object(Path, 'touch', side_effect=FileNotFoundError("Invalid filename")):
            result = runner._save_agent_data(invalid_name)
            
            assert result is None
            mock_logger.warning.assert_called_once_with("Error saving agent data")

def test_save_agent_data_returns_path_object(mock_dependencies):
    """Test _save_agent_data returns a Path object."""
    runner = Session(name="path_test")
    
    result = runner._save_agent_data("path_test")
    
    assert isinstance(result, Path)
    assert str(result).endswith(".json")
    
    # Cleanup
    if result and result.exists():
        result.unlink()

# ================ END Session: _save_agent_data Tests ===============
