import pytest
from unittest.mock import MagicMock, patch, call
import asyncio
from requestcompletion.run import Runner, RunnerCreationError, RunnerNotFoundError

# ================= START Mock Fixture ============
@pytest.fixture
def mock_dependencies(monkeypatch):
    m_prepare_logger = MagicMock()
    m_get_global_config = MagicMock()
    m_RCPublisher = MagicMock()
    m_ExecutionInfo = MagicMock(create_new=MagicMock())
    m_Coordinator = MagicMock()
    m_RCState = MagicMock()
    m_register_globals = MagicMock()
    m_delete_globals = MagicMock()
    m_detach_logging_handlers = MagicMock()

    monkeypatch.setattr('requestcompletion.run.prepare_logger', m_prepare_logger)
    monkeypatch.setattr('requestcompletion.run.get_global_config', m_get_global_config)
    monkeypatch.setattr('requestcompletion.run.RCPublisher', m_RCPublisher)
    monkeypatch.setattr('requestcompletion.run.ExecutionInfo', m_ExecutionInfo)
    monkeypatch.setattr('requestcompletion.run.Coordinator', m_Coordinator)
    monkeypatch.setattr('requestcompletion.run.RCState', m_RCState)
    monkeypatch.setattr('requestcompletion.run.register_globals', m_register_globals)
    monkeypatch.setattr('requestcompletion.run.delete_globals', m_delete_globals)
    monkeypatch.setattr('requestcompletion.run.detach_logging_handlers', m_detach_logging_handlers)

    return {
        'prepare_logger': m_prepare_logger,
        'get_global_config': m_get_global_config,
        'RCPublisher': m_RCPublisher,
        'ExecutionInfo': m_ExecutionInfo,
        'Coordinator': m_Coordinator,
        'RCState': m_RCState,
        'register_globals': m_register_globals,
        'delete_globals': m_delete_globals,
        'detach_logging_handlers': m_detach_logging_handlers,
    }
# ================ END Mock Fixture ===============

# ================= START Runner: Construction & Context Manager ============
def test_runner_construction_with_explicit_config_and_context(mock_dependencies):
    config = MagicMock()
    context = {'foo': 'bar'}
    # Setup mocks with needed API
    pub_mock = mock_dependencies['RCPublisher'].return_value
    state_mock = mock_dependencies['RCState'].return_value
    info_mock = MagicMock()
    state_mock.info = info_mock

    # Should not raise
    r = Runner(executor_config=config, context=context)
    assert r.executor_config == config
    assert hasattr(r, 'publisher')
    assert hasattr(r, 'rc_state')
    assert hasattr(r, 'coordinator')
    assert r.rc_state.info == info_mock

def test_runner_construction_with_defaults(mock_dependencies):
    # Should call get_global_config()
    Runner()
    assert mock_dependencies['get_global_config'].called

def test_runner_context_manager_closes_on_exit(mock_dependencies):
    config = MagicMock()
    context = {}
    runner = Runner(executor_config=config, context=context)
    with patch.object(runner, "_close") as mock_close:
        with runner:
            pass
        mock_close.assert_called_once()

# ================ END Runner: Construction & Context Manager ===============


# ================= START Runner: Singleton/Instance Id Behavior ============

def test_runner_identifier_is_taken_from_executor_config(mock_dependencies):
    config = MagicMock()
    config.run_identifier = "abc123"
    r = Runner(executor_config=config)
    assert r._identifier == "abc123"

# ================ END Runner: Singleton/Instance Id Behavior ===============


# ================= START Runner: setup_subscriber ===============

def test_setup_subscriber_adds_subscriber_if_present(mock_dependencies):
    config = MagicMock()
    config.subscriber = lambda s: None
    runner = Runner(executor_config=config)
    runner.publisher = MagicMock()
    with patch('requestcompletion.run.stream_subscriber', return_value="fake_stream_sub") as m_stream:
        runner.setup_subscriber()
        runner.publisher.subscribe.assert_called_once_with(
            "fake_stream_sub", name="Streaming Subscriber"
        )
        m_stream.assert_called_once_with(config.subscriber)

def test_setup_subscriber_noop_if_no_subscriber(mock_dependencies):
    config = MagicMock()
    config.subscriber = None
    runner = Runner(executor_config=config)
    runner.publisher = MagicMock()
    with patch('requestcompletion.run.stream_subscriber') as m_stream:
        runner.setup_subscriber()
        runner.publisher.subscribe.assert_not_called()
        m_stream.assert_not_called()

# ================ END Runner: setup_subscriber ===============


# ================= START Runner: _close & __exit__ ===============

def test_close_calls_shutdown_detach_delete(mock_dependencies):
    config = MagicMock()
    runner = Runner(executor_config=config)
    runner.rc_state = MagicMock()
    runner._close()
    assert runner.rc_state.shutdown.called
    assert mock_dependencies['detach_logging_handlers'].called
    assert mock_dependencies['delete_globals'].called

# ================ END Runner: _close & __exit__ ===============


# ================= START Runner: info property ===============

def test_info_property_returns_rc_state_info(mock_dependencies):
    config = MagicMock()
    runner = Runner(executor_config=config)
    rc_info = MagicMock()
    runner.rc_state.info = rc_info
    assert runner.info is rc_info

# ================ END Runner: info property ===============


# ================= START Runner: run_sync ===============

def test_run_sync_calls_asyncio_run_and_returns_info(mock_dependencies):
    config = MagicMock()
    runner = Runner(executor_config=config)
    runner.rc_state.info = "the-info"
    with patch('requestcompletion.run.asyncio.run', return_value=None) as m_async_run, \
         patch('requestcompletion.run.call', return_value=None) as m_call:
        result = runner.run_sync(lambda: "a")
        m_async_run.assert_called_once()
        m_call.assert_called_once()
        assert result == "the-info"

# ================ END Runner: run_sync ===============


# ================= START Runner: call and run async ===============

@pytest.mark.asyncio
async def test_call_method_calls_call_func(mock_dependencies):
    config = MagicMock()
    runner = Runner(executor_config=config)
    # Now patch call
    the_node = lambda: None
    result_value = MagicMock()
    with patch('requestcompletion.run.call', return_value=result_value) as m_call:
        out = await runner.call(the_node, 42, foo="bar")
        m_call.assert_called_once_with(the_node, 42, foo="bar")
        assert out == result_value

@pytest.mark.asyncio
async def test_run_method_runs_and_returns_info(mock_dependencies):
    config = MagicMock()
    runner = Runner(executor_config=config)
    runner.rc_state.info = "async-info"
    the_node = lambda: None
    with patch.object(runner, 'call', return_value=None) as m_call:
        result = await runner.run(the_node, 1, foo=2)
        m_call.assert_called_once_with(the_node, 1, foo=2)
        assert result == "async-info"

# ================ END Runner: call and run async ===============


# ================= START Runner: cancel & from_state ===============

def test_cancel_is_not_implemented(mock_dependencies):
    config = MagicMock()
    runner = Runner(executor_config=config)
    with pytest.raises(NotImplementedError):
        asyncio.run(runner.cancel("some-node-id"))

def test_from_state_is_not_implemented(mock_dependencies):
    config = MagicMock()
    runner = Runner(executor_config=config)
    with pytest.raises(NotImplementedError):
        runner.from_state(MagicMock())

# ================ END Runner: cancel & from_state ===============