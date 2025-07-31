from pathlib import Path

import pytest
from unittest.mock import MagicMock, patch, call, PropertyMock, Mock
import asyncio
from railtracks.session import Session

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

    monkeypatch.setattr('railtracks.session.prepare_logger', m_prepare_logger)
    monkeypatch.setattr('railtracks.session.get_global_config', m_get_global_config)
    monkeypatch.setattr('railtracks.session.RTPublisher', m_RTPublisher)
    monkeypatch.setattr('railtracks.session.ExecutionInfo', m_ExecutionInfo)
    monkeypatch.setattr('railtracks.session.Coordinator', m_Coordinator)
    monkeypatch.setattr('railtracks.session.RTState', m_RTState)
    monkeypatch.setattr('railtracks.session.register_globals', m_register_globals)
    monkeypatch.setattr('railtracks.session.delete_globals', m_delete_globals)
    monkeypatch.setattr('railtracks.session.detach_logging_handlers', m_detach_logging_handlers)

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
    assert hasattr(r, 'rc_state')
    assert hasattr(r, 'coordinator')
    assert r.rc_state.info == info_mock

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

    r = Session(run_identifier=run_id)
    assert r._identifier == run_id

# ================ END Session: Singleton/Instance Id Behavior ===============


# ================= START Session: setup_subscriber ===============

def test_setup_subscriber_adds_subscriber_if_present():
    sub_subscriber = Mock()
    runner = Session(broadcast_callback=sub_subscriber)
    runner.publisher = MagicMock()
    with patch('railtracks.session.stream_subscriber', return_value="fake_stream_sub") as m_stream:
        runner._setup_subscriber()
        runner.publisher.subscribe.assert_called_once_with(
            "fake_stream_sub", name="Streaming Subscriber"
        )
        m_stream.assert_called_once_with(sub_subscriber)

def test_setup_subscriber_noop_if_no_subscriber(mock_dependencies):
    runner = Session()
    runner.executor_config.subscriber = None
    runner.publisher = MagicMock()
    with patch('railtracks.session.stream_subscriber') as m_stream:
        runner._setup_subscriber()
        runner.publisher.subscribe.assert_not_called()
        m_stream.assert_not_called()

# ================ END Session: setup_subscriber ===============


# ================= START Session: _close & __exit__ ===============

def test_close_calls_shutdown_detach_delete(mock_dependencies):

    runner = Session()
    runner.rc_state = MagicMock()
    runner._close()
    assert runner.rc_state.shutdown.called
    assert mock_dependencies['detach_logging_handlers'].called
    assert mock_dependencies['delete_globals'].called

# ================ END Session: _close & __exit__ ===============


# ================= START Session: info property ===============

def test_info_property_returns_rc_state_info(mock_dependencies):
    runner = Session()
    rt_info = MagicMock()
    runner.rc_state.info = rt_info
    assert runner.info is rt_info

# ================ END Session: info property ===============


# ================ START Session: run_sync ===============

def test_run_sync_calls_asyncio_run_and_returns_info(mock_dependencies):

    runner = Session()
    runner.rc_state.info = "the-info"
    with patch('railtracks.session.asyncio.run', return_value=None) as m_async_run, \
         patch('railtracks.session.call', return_value=None) as m_call:
        result = runner.run_sync(lambda: "a")
        m_async_run.assert_called_once()
        m_call.assert_called_once()
        assert result == "the-info"

# ================ END Session: run_sync ===============


# ================= START Session: call and run async ===============

@pytest.mark.asyncio
async def test_call_method_calls_call_func(mock_dependencies):
    runner = Session()
    # Now patch call
    the_node = lambda: None
    result_value = MagicMock()
    # flagging this becuase I envision us having a dumb bug if we ever change the import statement in that source file.
    with patch('railtracks.session.call', return_value=result_value) as m_call:
        out = await runner.call(the_node, 42, foo="bar")
        m_call.assert_called_once_with(the_node, 42, foo="bar")
        assert out == result_value

@pytest.mark.asyncio
async def test_run_method_runs_and_returns_info(mock_dependencies):
    runner = Session()
    runner.rc_state.info = "async-info"
    the_node = lambda: None
    # flagging this becuase I envision us having a dumb bug if we ever change the import statement in that source file.
    with patch('railtracks.session.call', return_value=None) as m_call:
        result = await runner.run(the_node, 1, foo=2)
        m_call.assert_called_once_with(the_node, 1, foo=2)
        assert result == "async-info"

# ================ END Session: call and run async ===============




# ================= START Session: Check saved data ===============
def test_runner_saves_data():
    run_id = "abs53562j12h267"

    serialization_mock = '{"Key": "Value"}'
    info = MagicMock()
    info.graph_serialization.return_value = serialization_mock


    with patch.object(Session, 'info', new_callable=PropertyMock) as mock_runner:
        mock_runner.return_value.graph_serialization.return_value = serialization_mock

        r = Session(
            run_identifier=run_id,
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

        r = Session(run_identifier=run_id, save_state=False)
        r.__exit__(None, None, None)




    path = Path(".railtracks") / f"{run_id}.json"
    assert not path.is_file()
