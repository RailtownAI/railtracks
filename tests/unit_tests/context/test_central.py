import pytest
from unittest import mock

import requestcompletion.context.central as central

# ============ START Runner Context Tests ===============
def test_safe_get_runner_context_raises_when_none():
    central.delete_globals()
    with pytest.raises(central.ContextError):
        central.safe_get_runner_context()

def test_is_context_present_and_active(monkeypatch, make_runner_context_vars):
    rc = make_runner_context_vars()
    monkeypatch.setattr(central, "runner_context", mock.Mock(get=mock.Mock(return_value=rc)))
    assert central.is_context_present()
    assert central.is_context_active()
# ============ END Runner Context Tests ===============

# ============ START Publisher Tests ===============
def test_get_publisher_returns_publisher(monkeypatch, make_internal_context_mock, make_runner_context_vars):
    pub = mock.Mock()
    rc = make_runner_context_vars(internal_context=make_internal_context_mock(publisher=pub))
    monkeypatch.setattr(central, "runner_context", mock.Mock(get=mock.Mock(return_value=rc)))
    assert central.get_publisher() is pub

@pytest.mark.asyncio
async def test_activate_publisher(monkeypatch, make_runner_context_vars, make_internal_context_mock):
    pub = mock.AsyncMock()
    ic = make_internal_context_mock(publisher=pub)
    rc = make_runner_context_vars(internal_context=ic)
    monkeypatch.setattr(central, "safe_get_runner_context", mock.Mock(return_value=rc))
    await central.activate_publisher()
    pub.start.assert_awaited_once()

@pytest.mark.asyncio
async def test_shutdown_publisher(monkeypatch, make_runner_context_vars, make_internal_context_mock):
    pub = mock.AsyncMock()
    pub.is_running.return_value = True
    ic = make_internal_context_mock(publisher=pub)
    rc = make_runner_context_vars(internal_context=ic)
    monkeypatch.setattr(central, "safe_get_runner_context", mock.Mock(return_value=rc))
    await central.shutdown_publisher()
    pub.shutdown.assert_awaited_once()
# ============ END Publisher Tests ===============

# ============ START ID Accessor Tests ===============
def test_get_runner_id(monkeypatch, make_runner_context_vars):
    rc = make_runner_context_vars(runner_id="runner-xyz")
    monkeypatch.setattr(central, "runner_context", mock.Mock(get=mock.Mock(return_value=rc)))
    assert central.get_runner_id() == "runner-xyz"

def test_get_parent_id(monkeypatch, make_runner_context_vars, make_internal_context_mock):
    rc = make_runner_context_vars(internal_context=make_internal_context_mock(parent_id="parent-abc"))
    monkeypatch.setattr(central, "runner_context", mock.Mock(get=mock.Mock(return_value=rc)))
    assert central.get_parent_id() == "parent-abc"
# ============ END ID Accessor Tests ===============

# ============ START Globals Registration/Deletion Tests ===============
def test_register_globals_sets_context(monkeypatch):
    monkeypatch.setattr(central, "runner_context", mock.Mock(set=mock.Mock()))
    monkeypatch.setattr(central, "InternalContext", mock.Mock(return_value="ic"))
    monkeypatch.setattr(central, "MutableExternalContext", mock.Mock(return_value="ec"))
    monkeypatch.setattr(central, "RunnerContextVars", mock.Mock())
    central.register_globals(
        runner_id="r1",
        rc_publisher=None,
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
    rc = make_runner_context_vars(internal_context=make_internal_context_mock(executor_config=config))
    monkeypatch.setattr(central, "safe_get_runner_context", mock.Mock(return_value=rc))
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
        central.set_config(config)
    central.global_executor_config.set.assert_called_with(config)

def test_set_streamer_warns(monkeypatch):
    config = mock.Mock()
    monkeypatch.setattr(central, "is_context_active", mock.Mock(return_value=True))
    monkeypatch.setattr(central, "global_executor_config", mock.Mock(get=mock.Mock(return_value=config), set=mock.Mock()))
    def dummy_subscriber(x): pass
    with pytest.warns(UserWarning):
        central.set_streamer(dummy_subscriber)
    assert config.subscriber == dummy_subscriber
    central.global_executor_config.set.assert_called_with(config)
# ============ END Config Tests ===============

# ============ START Parent/Context Update Tests ===============
def test_update_parent_id(monkeypatch, make_runner_context_vars):
    rc = make_runner_context_vars()
    rc.prepare_new = mock.Mock(return_value="new_ctx")
    monkeypatch.setattr(central, "safe_get_runner_context", mock.Mock(return_value=rc))
    monkeypatch.setattr(central, "runner_context", mock.Mock(set=mock.Mock()))
    central.update_parent_id("new-parent")
    rc.prepare_new.assert_called_with("new-parent")
    central.runner_context.set.assert_called_with("new_ctx")

def test_runner_context_vars_prepare_new(make_external_context_mock, make_internal_context_mock):
    """Test RunnerContextVars.prepare_new creates a new context with updated parent_id."""
    old_parent_id = "parent-1"
    new_parent_id = "parent-2"
    internal_context = make_internal_context_mock(parent_id=old_parent_id)
    # Mock prepare_new to return a new mock with updated parent_id
    new_internal_context = make_internal_context_mock(parent_id=new_parent_id)
    internal_context.prepare_new.return_value = new_internal_context
    rc = central.RunnerContextVars(
        runner_id="runner-x",
        internal_context=internal_context,
        external_context=make_external_context_mock(),
    )
    new_rc = rc.prepare_new(new_parent_id)
    assert new_rc.internal_context.parent_id == new_parent_id
    assert new_rc.runner_id == rc.runner_id
    assert new_rc.external_context == rc.external_context
# ============ END Parent/Context Update Tests ===============

# ============ START External Context Access Tests ===============
def test_get_and_put(monkeypatch, make_runner_context_vars, make_external_context_mock):
    ec = make_external_context_mock()
    rc = make_runner_context_vars(external_context=ec)
    monkeypatch.setattr(central, "safe_get_runner_context", mock.Mock(return_value=rc))
    assert central.get("foo") == "bar"
    assert central.get("notfound", default=123) == 123
    central.put("baz", 42)
    ec.put.assert_called_with("baz", 42)
# ============ END External Context Access Tests ===============
