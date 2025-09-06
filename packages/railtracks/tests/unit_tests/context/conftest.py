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
def make_internal_context_mock():
    def _make_internal_context_mock(**kwargs):
        ic = mock.Mock()
        ic.is_active = kwargs.get("is_active", True)
        ic.parent_id = kwargs.get("parent_id", "parent-123")
        ic.session_id = kwargs.get("session_id", "session-123")
        ic.executor_config = kwargs.get("executor_config", mock.Mock())
        ic.publisher = kwargs.get("publisher", mock.Mock())
        ic.prepare_new = mock.Mock(return_value=ic)
        return ic

    return _make_internal_context_mock


@pytest.fixture
def make_external_context_mock():
    def _make_external_context_mock():
        ec = mock.Mock()
        ec.get = mock.Mock(side_effect=lambda k, default=None: {"foo": "bar"}.get(k, default))
        ec.put = mock.Mock()
        return ec

    return _make_external_context_mock


@pytest.fixture
def make_runner_context_vars(make_internal_context_mock, make_external_context_mock):
    def _make_runner_context_vars(**kwargs):
        return central.RunnerContextVars(
            internal_context=kwargs.get("internal_context", make_internal_context_mock()),
            external_context=kwargs.get("external_context", make_external_context_mock()),
        )

    return _make_runner_context_vars