from pathlib import Path

import pytest
from unittest.mock import MagicMock, patch, call, PropertyMock, Mock
import asyncio
import railtracks as rt
from railtracks import Session, session

# ================= START Mock Fixture ============
@pytest.fixture
def mock_dependencies(monkeypatch):
    m_prepare_logger = MagicMock()
    m_get_global_config = MagicMock()
    m_RTPublisher = MagicMock()
    m_ExecutionInfo = MagicMock(create_new=MagicMock())
    m_Coordinator = MagicMock()
    m_RTState = MagicMock()
    m_register_globals = MagicMock()
    m_delete_globals = MagicMock()
    m_detach_logging_handlers = MagicMock()

    monkeypatch.setattr('railtracks._session.prepare_logger', m_prepare_logger)
    monkeypatch.setattr('railtracks._session.get_global_config', m_get_global_config)
    monkeypatch.setattr('railtracks._session.RTPublisher', m_RTPublisher)
    monkeypatch.setattr('railtracks._session.ExecutionInfo', m_ExecutionInfo)
    monkeypatch.setattr('railtracks._session.Coordinator', m_Coordinator)
    monkeypatch.setattr('railtracks._session.RTState', m_RTState)
    monkeypatch.setattr('railtracks._session.register_globals', m_register_globals)
    monkeypatch.setattr('railtracks._session.delete_globals', m_delete_globals)
    monkeypatch.setattr('railtracks._session.detach_logging_handlers', m_detach_logging_handlers)

    return {
        'prepare_logger': m_prepare_logger,
        'get_global_config': m_get_global_config,
        'RTPublisher': m_RTPublisher,
        'ExecutionInfo': m_ExecutionInfo,
        'Coordinator': m_Coordinator,
        'RTState': m_RTState,
        'register_globals': m_register_globals,
        'delete_globals': m_delete_globals,
        'detach_logging_handlers': m_detach_logging_handlers,
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

def test_runner_identifier_is_taken_from_executor_config():
    run_id = "abc123"

    r = Session(identifier=run_id)
    assert r._identifier == run_id

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

def test_close_calls_shutdown_detach_delete(mock_dependencies):

    runner = Session()
    runner.rt_state = MagicMock()
    runner._close()
    assert runner.rt_state.shutdown.called
    assert mock_dependencies['detach_logging_handlers'].called
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
def test_runner_saves_data():
    run_id = "abs53562j12h267"

    serialization_mock = '{"Key": "Value"}'
    info = MagicMock()
    info.graph_serialization.return_value = serialization_mock


    with patch.object(Session, 'info', new_callable=PropertyMock) as mock_runner:
        mock_runner.return_value.graph_serialization.return_value = serialization_mock

        r = Session(
            identifier=run_id,
            save_state=True,
        )
        r.__exit__(None, None, None)


    path = Path(".railtracks") / f"{run_id}.json"
    assert path.read_text() == serialization_mock


def test_runner_not_saves_data():
    config = MagicMock()

    run_id = "Run 2"
    config.run_identifier = run_id
    config.save_state = False

    serialization_mock = '{"Key": "Value"}'
    info = MagicMock()
    info.graph_serialization.return_value = serialization_mock

    with patch.object(Session, 'info', new_callable=PropertyMock) as mock_runner:
        mock_runner.return_value.graph_serialization.return_value = serialization_mock

        r = Session(identifier=run_id, save_state=False)
        r.__exit__(None, None, None)




    path = Path(".railtracks") / f"{run_id}.json"
    assert not path.is_file()


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
        logging_setting="DEBUG"
    )
    assert callable(decorator)

@pytest.mark.asyncio
async def test_session_decorator_wraps_async_function(mock_dependencies):
    """Test that the decorator properly wraps an async function."""
    @session(timeout=10)
    async def test_function():
        return "test_result"
    
    result = await test_function()
    assert result == "test_result"

@pytest.mark.asyncio
async def test_session_decorator_with_function_args(mock_dependencies):
    """Test that the decorator preserves function arguments."""
    @session()
    async def test_function(arg1, arg2, kwarg1=None):
        return f"{arg1}-{arg2}-{kwarg1}"
    
    result = await test_function("a", "b", kwarg1="c")
    assert result == "a-b-c"

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
        
        await test_function()
    
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

# ================ END Session: Decorator Tests ===============
