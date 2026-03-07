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
    m_get_global_config = MagicMock()
    m_RTPublisher = MagicMock()
    m_ExecutionInfo = MagicMock(create_new=MagicMock())
    m_Coordinator = MagicMock()
    m_RTState = MagicMock()
    m_register_globals = MagicMock()
    m_delete_globals = MagicMock()

    monkeypatch.setattr('railtracks._session.get_global_config', m_get_global_config)
    monkeypatch.setattr('railtracks._session.RTPublisher', m_RTPublisher)
    monkeypatch.setattr('railtracks._session.ExecutionInfo', m_ExecutionInfo)
    monkeypatch.setattr('railtracks._session.Coordinator', m_Coordinator)
    monkeypatch.setattr('railtracks._session.RTState', m_RTState)
    monkeypatch.setattr('railtracks._session.register_globals', m_register_globals)
    monkeypatch.setattr('railtracks._session.delete_globals', m_delete_globals)

    return {
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

def test_runner_context_manager_closes_on_exit(mock_dependencies, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

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

# ================ END Session: _close & __exit__ ===============


# ================= START Session: info property ===============

def test_info_property_returns_rt_state_info(mock_dependencies):
    runner = Session()
    rt_info = MagicMock()
    runner.rt_state.info = rt_info
    assert runner.info is rt_info

# ================ END Session: info property ===============


# ================= START Session: Check saved data ===============
# tmp_path is a pytest fixture that provides a temporary directory, built in to pytest
def test_session_saves_data(tmp_path, monkeypatch):
    """Test that session saves execution data to JSON file in temp directory."""
    name = "abs53562j12h267"
    monkeypatch.setenv("RAILTRACKS_ALLOW_PERSISTENCE", "1")
    monkeypatch.chdir(tmp_path)

    serialization_mock = {"Key": "Value"}

    with patch.object(Session, 'info', new_callable=PropertyMock) as mock_info:
        mock_info.return_value.graph_serialization.return_value = serialization_mock

        r = Session(name=name, save_state=True)
        r.__exit__(None, None, None)

        # Verify file was created in temp directory
        sessions_dir = tmp_path / ".railtracks" / "data" / "sessions"
        assert sessions_dir.exists(), f"Sessions directory not created at {sessions_dir}"
        
        files = list(sessions_dir.glob("*.json"))
        assert len(files) == 1, f"Expected 1 file, found {len(files)}"
        
        file_path = files[0]
        assert file_path.name.startswith(f"{name}_"), f"Unexpected filename: {file_path.name}"
        assert r._identifier in file_path.name, f"Session ID not in filename: {file_path.name}"
        
        # Verify file has content
        content = json.loads(file_path.read_text())
        assert "runs" in content, f"'runs' key missing from saved data"
        assert content["runs"] == serialization_mock, f"Serialization data mismatch"
        assert content["session_name"] == name, f"Session name mismatch"
        assert "session_id" in content, f"'session_id' key missing from saved data"


def test_session_not_saves_data(tmp_path, monkeypatch):
    """Test that session does not save data when save_state=False."""
    monkeypatch.chdir(tmp_path)
    
    serialization_mock = '{"Key": "Value"}'
    run_id = "Run 2"

    with patch.object(Session, 'info', new_callable=PropertyMock) as mock_info:
        mock_info.return_value.graph_serialization.return_value = serialization_mock

        r = Session(name=run_id, save_state=False)
        r.__exit__(None, None, None)

    # Verify no files were created
    sessions_dir = tmp_path / ".railtracks" / "data" / "sessions"
    if sessions_dir.exists():
        files = list(sessions_dir.glob("*.json"))
        assert len(files) == 0, f"Expected no files to be created, but found {len(files)}"
    # If directory doesn't exist, that's also fine - nothing was saved


def test_session_fallback_on_invalid_name(tmp_path, monkeypatch):
    """Test that session falls back to identifier-only filename when name causes issues."""
    monkeypatch.setenv("RAILTRACKS_ALLOW_PERSISTENCE", "1")
    monkeypatch.chdir(tmp_path)
    
    # Use a name that would cause issues in file path creation
    invalid_name = "test/invalid:name*with|bad<chars>"

    serialization_mock = {"Key": "Value"}

    with patch.object(Session, 'info', new_callable=PropertyMock) as mock_info:
        mock_info.return_value.graph_serialization.return_value = serialization_mock

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
            for warning_call in warning_calls:
                if "falling back to using the unique identifier only" in warning_call:
                    fallback_warning = warning_call
                    break

            assert fallback_warning is not None, "Expected fallback warning not found"
            assert invalid_name in fallback_warning

            # Verify that the fallback file was created (identifier only) in temp directory
            sessions_dir = tmp_path / ".railtracks" / "data" / "sessions"
            assert sessions_dir.exists(), f"Sessions directory not created at {sessions_dir}"
            
            fallback_path = sessions_dir / f"{r._identifier}.json"
            assert fallback_path.exists(), f"Fallback file not created at {fallback_path}"
            
            # Verify file has content
            content = json.loads(fallback_path.read_text())
            assert "runs" in content, f"'runs' key missing from saved data"


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
    )
    assert callable(decorator)

@pytest.mark.asyncio
async def test_session_decorator_wraps_async_function(mock_dependencies, tmp_path, monkeypatch):
    """Test that the decorator properly wraps an async function and returns tuple."""
    monkeypatch.chdir(tmp_path)
    
    @session(timeout=10)
    async def test_function():
        return "test_result"

    result, session_obj = await test_function()
    assert result == "test_result"
    assert isinstance(session_obj, Session)

@pytest.mark.asyncio
async def test_session_decorator_with_function_args(mock_dependencies, tmp_path, monkeypatch):
    """Test that the decorator preserves function arguments and returns tuple."""
    monkeypatch.chdir(tmp_path)
    
    @session()
    async def test_function(arg1, arg2, kwarg1=None):
        return f"{arg1}-{arg2}-{kwarg1}"

    result, session_obj = await test_function("a", "b", kwarg1="c")
    assert result == "a-b-c"
    assert isinstance(session_obj, Session)

@pytest.mark.asyncio
async def test_session_decorator_context_manager_behavior(mock_dependencies, tmp_path, monkeypatch):
    """Test that the decorator properly manages session lifecycle."""
    monkeypatch.chdir(tmp_path)
    
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
async def test_session_decorator_returns_session_object(mock_dependencies, tmp_path, monkeypatch):
    """Test that decorator returns both result and session object with access to session info."""
    monkeypatch.chdir(tmp_path)
    
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
async def test_session_decorator_handles_tuple_returns(mock_dependencies, tmp_path, monkeypatch):
    """Test that decorator properly handles functions that return tuples."""
    monkeypatch.chdir(tmp_path)
    
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
