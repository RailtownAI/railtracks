import pytest
from unittest import mock

import railtracks.context.central as central
from railtracks.context.session_context import ScopeEntry, ScopeKind
from railtracks.utils.config import ExecutorConfig

# ============ START Session Context Tests ===============
def test_safe_get_runner_context_raises_when_none():
    central.delete_globals()
    with pytest.raises(central.ContextError):
        central.safe_get_runner_context()

def test_is_context_present_and_active(monkeypatch, make_runner_context_vars):
    rt = make_runner_context_vars()
    monkeypatch.setattr(central, "runner_context", mock.Mock(get=mock.Mock(return_value=rt)))
    assert central.is_context_present()
    assert central.is_context_active()
# ============ END Session Context Tests ===============

# ============ START Publisher Tests ===============
def test_get_publisher_returns_publisher(monkeypatch, make_session_context_mock, make_runner_context_vars):
    pub = mock.Mock()
    rt = make_runner_context_vars(session_context=make_session_context_mock(publisher=pub))
    monkeypatch.setattr(central, "runner_context", mock.Mock(get=mock.Mock(return_value=rt)))
    assert central.get_publisher() is pub

@pytest.mark.asyncio
async def test_activate_publisher(monkeypatch, make_runner_context_vars, make_session_context_mock):
    pub = mock.AsyncMock()
    sc = make_session_context_mock(publisher=pub)
    rt = make_runner_context_vars(session_context=sc)
    monkeypatch.setattr(central, "safe_get_runner_context", mock.Mock(return_value=rt))
    await central.activate_publisher()
    pub.start.assert_awaited_once()

@pytest.mark.asyncio
async def test_shutdown_publisher(monkeypatch, make_runner_context_vars, make_session_context_mock):
    pub = mock.AsyncMock()
    pub.is_running.return_value = True
    sc = make_session_context_mock(publisher=pub)
    rt = make_runner_context_vars(session_context=sc)
    monkeypatch.setattr(central, "safe_get_runner_context", mock.Mock(return_value=rt))
    await central.shutdown_publisher()
    pub.shutdown.assert_awaited_once()
# ============ END Publisher Tests ===============

# ============ START ID Accessor Tests ===============
def test_get_runner_id(monkeypatch, make_runner_context_vars, make_session_context_mock):
    assert central.session_id() is None
    session_context = make_session_context_mock(session_id="runner-xyz")
    rt = make_runner_context_vars(session_context=session_context)
    monkeypatch.setattr(central, "runner_context", mock.Mock(get=mock.Mock(return_value=rt)))
    assert central.get_session_id() == "runner-xyz"
    assert central.session_id() == "runner-xyz"

def test_get_parent_id(monkeypatch, make_runner_context_vars, make_session_context_mock):
    rt = make_runner_context_vars(session_context=make_session_context_mock(current_node_id="parent-abc"))
    monkeypatch.setattr(central, "runner_context", mock.Mock(get=mock.Mock(return_value=rt)))
    assert central.get_parent_id() == "parent-abc"

def test_get_middleware_id(monkeypatch, make_runner_context_vars, make_session_context_mock):
    rt = make_runner_context_vars(session_context=make_session_context_mock(current_middleware_id="mw-abc"))
    monkeypatch.setattr(central, "runner_context", mock.Mock(get=mock.Mock(return_value=rt)))
    assert central.get_middleware_id() == "mw-abc"
# ============ END ID Accessor Tests ===============

# ============ START Globals Registration/Deletion Tests ===============
def test_register_globals_sets_context(monkeypatch):
    monkeypatch.setattr(central, "runner_context", mock.Mock(set=mock.Mock()))
    monkeypatch.setattr(central, "SessionContext", mock.Mock(return_value="sc"))
    monkeypatch.setattr(central, "MutableExternalContext", mock.Mock(return_value="ec"))
    monkeypatch.setattr(central, "RunnerContextVars", mock.Mock())
    central.register_globals(
        session_id="r1",
        rt_publisher=None,
        executor_config=mock.Mock(),
        global_context_vars={"foo": "bar"},
    )
    assert central.runner_context.set.called

def test_delete_globals(monkeypatch):
    mock_ctx = mock.Mock(set=mock.Mock())
    monkeypatch.setattr(central, "runner_context", mock_ctx)
    central.delete_globals()
    mock_ctx.set.assert_called_with(None)
# ============ END Globals Registration/Deletion Tests ===============

# ============ START Config Tests ===============
def test_get_and_set_global_config(monkeypatch):
    config = mock.Mock()
    monkeypatch.setattr(central, "global_executor_config", mock.Mock(get=mock.Mock(return_value=config), set=mock.Mock()))
    assert central.get_global_config() is config
    central.set_global_config(config)
    central.global_executor_config.set.assert_called_with(config)

def test_get_and_set_local_config(monkeypatch, make_runner_context_vars, make_session_context_mock):
    config = mock.Mock()
    rt = make_runner_context_vars(session_context=make_session_context_mock(executor_config=config))
    monkeypatch.setattr(central, "safe_get_runner_context", mock.Mock(return_value=rt))
    assert central.get_local_config() is config
    # set_local_config should update context.executor_config and set runner_context
    monkeypatch.setattr(central, "runner_context", mock.Mock(set=mock.Mock()))
    central.set_local_config(config)
    central.runner_context.set.assert_called()

def test_set_config_warns(monkeypatch):
    config = mock.Mock()
    monkeypatch.setattr(central, "is_context_active", mock.Mock(return_value=True))
    monkeypatch.setattr(central, "global_executor_config", mock.Mock(set=mock.Mock()))
    with pytest.warns(UserWarning):
        central.set_config()
    central.global_executor_config.set.assert_called_once()


# ============ END Config Tests ===============

# ============ START ContextVarScopeManager Tests ===============
def _register(session_id="s1"):
    central.register_globals(
        session_id=session_id,
        rt_publisher=None,
        executor_config=ExecutorConfig(),
        global_context_vars={},
    )


def test_enter_node_establishes_run_id_on_first_entry():
    _register()
    manager = central.ContextVarScopeManager()

    assert central.get_run_id() is None

    with manager.enter_node("node-1"):
        assert central.get_run_id() == "node-1"
        assert central.get_parent_id() == "node-1"

    # reverted after exit
    assert central.get_run_id() is None
    assert central.get_parent_id() is None


def test_enter_node_keeps_existing_run_id_for_nested_node():
    _register()
    manager = central.ContextVarScopeManager()

    with manager.enter_node("node-1"):
        with manager.enter_node("node-2"):
            assert central.get_run_id() == "node-1"
            assert central.get_parent_id() == "node-2"
        assert central.get_parent_id() == "node-1"


def test_enter_node_body_reports_owning_node_id():
    _register()
    manager = central.ContextVarScopeManager()

    with manager.enter_node("node-1"):
        with manager.enter_node_body():
            assert central.get_parent_id() == "node-1"


def test_enter_node_body_requires_active_node_scope():
    _register()
    manager = central.ContextVarScopeManager()

    with pytest.raises(AssertionError):
        with manager.enter_node_body():
            pass


def test_enter_middleware_generates_fresh_id_and_reports_current_node():
    _register()
    manager = central.ContextVarScopeManager()

    with manager.enter_node("node-1"):
        with manager.enter_middleware("my-guard") as middleware_id:
            assert middleware_id is not None
            assert central.get_middleware_id() == middleware_id
            # a nested call fired from within middleware still resolves to the
            # enclosing node, not the middleware.
            assert central.get_parent_id() == "node-1"
        assert central.get_middleware_id() is None


def test_middleware_fired_node_lands_under_middleware():
    _register()
    manager = central.ContextVarScopeManager()

    with manager.enter_node("node-1"):
        with manager.enter_middleware("guard") as middleware_id:
            scope = central.get_current_scope()
            assert scope.value == ScopeEntry(ScopeKind.MIDDLEWARE, middleware_id, name="guard")
            with manager.enter_node("node-2"):
                # node-2's immediate parent scope entry is the middleware, not node-1
                assert central.get_current_scope().value.kind is ScopeKind.NODE
                assert central.get_current_scope().parent.value.kind is ScopeKind.MIDDLEWARE


def test_restore_scope_replaces_ambient_scope():
    _register()
    manager = central.ContextVarScopeManager()

    with manager.enter_node("node-1"):
        captured_scope = central.get_current_scope()
        captured_run_id = central.get_run_id()

    # ambient scope is back to None here
    assert central.get_parent_id() is None

    with central.restore_scope(captured_scope, captured_run_id):
        assert central.get_parent_id() == "node-1"
        assert central.get_run_id() == captured_run_id

    assert central.get_parent_id() is None
# ============ END ContextVarScopeManager Tests ===============

# ============ START External Context Access Tests ===============
def test_get_and_put(monkeypatch, make_runner_context_vars, make_external_context_mock):
    ec = make_external_context_mock()
    rt = make_runner_context_vars(external_context=ec)
    monkeypatch.setattr(central, "safe_get_runner_context", mock.Mock(return_value=rt))
    assert central.get("foo") == "bar"
    assert central.get("notfound", default=123) == 123
    central.put("baz", 42)
    ec.put.assert_called_with("baz", 42)
# ============ END External Context Access Tests ===============
