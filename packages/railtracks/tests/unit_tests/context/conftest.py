import pytest
from unittest import mock
import railtracks.context.central as central


@pytest.fixture
def dummy_executor_config():
    return mock.Mock()


@pytest.fixture(autouse=True)
def cleanup_globals():

    central.delete_globals()
    yield
    central.delete_globals()


@pytest.fixture
def make_session_context_mock():
    def _make_session_context_mock(**kwargs):
        sc = mock.Mock()
        sc.is_active = kwargs.get("is_active", True)
        sc.current_node_id = kwargs.get("current_node_id", "parent-123")
        sc.current_middleware_id = kwargs.get("current_middleware_id", None)
        sc.session_id = kwargs.get("session_id", "session-123")
        sc.run_id = kwargs.get("run_id", None)
        sc.scope = kwargs.get("scope", None)
        sc.executor_config = kwargs.get("executor_config", mock.Mock())
        sc.publisher = kwargs.get("publisher", mock.Mock())
        sc.with_scope_pushed = mock.Mock(return_value=sc)
        return sc

    return _make_session_context_mock


@pytest.fixture
def make_external_context_mock():
    def _make_external_context_mock():
        ec = mock.Mock()
        ec.get = mock.Mock(side_effect=lambda k, default=None: {"foo": "bar"}.get(k, default))
        ec.put = mock.Mock()
        return ec

    return _make_external_context_mock


@pytest.fixture
def make_runner_context_vars(make_session_context_mock, make_external_context_mock):
    def _make_runner_context_vars(**kwargs):
        return central.RunnerContextVars(
            session_context=kwargs.get("session_context", make_session_context_mock()),
            external_context=kwargs.get("external_context", make_external_context_mock()),
        )

    return _make_runner_context_vars
