import pytest
from unittest import mock

import railtracks.context.central as central
from requests import session

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
def test_get_publisher_returns_publisher(monkeypatch, make_internal_context_mock, make_runner_context_vars):
    pub = mock.Mock()
    rt = make_runner_context_vars(internal_context=make_internal_context_mock(publisher=pub))
    monkeypatch.setattr(central, "runner_context", mock.Mock(get=mock.Mock(return_value=rt)))
    assert central.get_publisher() is pub

@pytest.mark.asyncio
async def test_activate_publisher(monkeypatch, make_runner_context_vars, make_internal_context_mock):
    pub = mock.AsyncMock()
    ic = make_internal_context_mock(publisher=pub)
    rt = make_runner_context_vars(internal_context=ic)
    monkeypatch.setattr(central, "safe_get_runner_context", mock.Mock(return_value=rt))
    await central.activate_publisher()
    pub.start.assert_awaited_once()

@pytest.mark.asyncio
async def test_shutdown_publisher(monkeypatch, make_runner_context_vars, make_internal_context_mock):
    pub = mock.AsyncMock()
    pub.is_running.return_value = True
    ic = make_internal_context_mock(publisher=pub)
    rt = make_runner_context_vars(internal_context=ic)
    monkeypatch.setattr(central, "safe_get_runner_context", mock.Mock(return_value=rt))
    await central.shutdown_publisher()
    pub.shutdown.assert_awaited_once()
# ============ END Publisher Tests ===============

# ============ START ID Accessor Tests ===============
def test_get_runner_id(monkeypatch, make_runner_context_vars, make_internal_context_mock):
    assert central.session_id() is None
    internal_context = make_internal_context_mock(session_id="runner-xyz")
    rt = make_runner_context_vars(internal_context=internal_context)
    monkeypatch.setattr(central, "runner_context", mock.Mock(get=mock.Mock(return_value=rt)))
    assert central.get_session_id() == "runner-xyz"
    assert central.session_id() == "runner-xyz"

def test_get_parent_id(monkeypatch, make_runner_context_vars, make_internal_context_mock):
    rt = make_runner_context_vars(internal_context=make_internal_context_mock(parent_id="parent-abc"))
    monkeypatch.setattr(central, "runner_context", mock.Mock(get=mock.Mock(return_value=rt)))
    assert central.get_parent_id() == "parent-abc"
# ============ END ID Accessor Tests ===============

# ============ START Globals Registration/Deletion Tests ===============
def test_register_globals_sets_context(monkeypatch):
    monkeypatch.setattr(central, "runner_context", mock.Mock(set=mock.Mock()))
    monkeypatch.setattr(central, "InternalContext", mock.Mock(return_value="ic"))
    monkeypatch.setattr(central, "MutableExternalContext", mock.Mock(return_value="ec"))
    monkeypatch.setattr(central, "RunnerContextVars", mock.Mock())
    central.register_globals(
        session_id="r1",
        rt_publisher=None,
        parent_id=None,
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

def test_get_and_set_local_config(monkeypatch, make_runner_context_vars, make_internal_context_mock):
    config = mock.Mock()
    rt = make_runner_context_vars(internal_context=make_internal_context_mock(executor_config=config))
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

# ============ START Parent/Context Update Tests ===============
def test_update_parent_id(monkeypatch, make_runner_context_vars):
    rt = make_runner_context_vars()
    rt.prepare_new = mock.Mock(return_value="new_ctx")
    monkeypatch.setattr(central, "safe_get_runner_context", mock.Mock(return_value=rt))
    monkeypatch.setattr(central, "runner_context", mock.Mock(set=mock.Mock()))
    central.update_parent_id("new-parent")
    rt.prepare_new.assert_called_with("new-parent", new_run_id=None)
    central.runner_context.set.assert_called_with("new_ctx")

def test_runner_context_vars_prepare_new(make_external_context_mock, make_internal_context_mock):
    """Test RunnerContextVars.prepare_new creates a new context with updated parent_id."""
    old_parent_id = "parent-1"
    new_parent_id = "parent-2"
    internal_context = make_internal_context_mock(parent_id=old_parent_id)
    # Mock prepare_new to return a new mock with updated parent_id
    new_internal_context = make_internal_context_mock(parent_id=new_parent_id)
    internal_context.prepare_new.return_value = new_internal_context
    rt = central.RunnerContextVars(    
        internal_context=internal_context,
        external_context=make_external_context_mock(),
    )
    new_rt = rt.prepare_new(new_parent_id)
    assert new_rt.internal_context.parent_id == new_parent_id
    assert new_rt.internal_context.session_id == rt.internal_context.session_id
    assert new_rt.external_context == rt.external_context
# ============ END Parent/Context Update Tests ===============

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
