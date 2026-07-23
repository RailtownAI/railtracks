
import pytest
from unittest import mock
from railtracks.context.session_context import ScopeEntry, ScopeKind, SessionContext

# ============ START DummyPublisher Helper ===============
class DummyPublisher:
    def __init__(self, running=True):
        self._running = running
    def is_running(self):
        return self._running
# ============ END DummyPublisher Helper ===============

# ============ START SessionContext Property Tests ===============
def test_session_context_properties(dummy_executor_config):
    pub = DummyPublisher()
    ctx = SessionContext(
        session_id="runner-1",
        publisher=pub,
        executor_config=dummy_executor_config,
    )
    assert ctx.session_id == "runner-1"
    assert ctx.publisher is pub
    assert ctx.executor_config is dummy_executor_config
    assert ctx.is_active is True
    assert ctx.current_node_id is None
    assert ctx.current_middleware_id is None
# ============ END SessionContext Property Tests ===============

# ============ START SessionContext Setter Tests ===============
def test_session_context_setters(dummy_executor_config):
    ctx = SessionContext(
        session_id=None,
        publisher=None,
        executor_config=dummy_executor_config,
    )
    ctx.session_id = "r2"
    pub = DummyPublisher()
    ctx.publisher = pub
    new_config = mock.Mock()
    ctx.executor_config = new_config
    assert ctx.session_id == "r2"
    assert ctx.publisher is pub
    assert ctx.executor_config is new_config
# ============ END SessionContext Setter Tests ===============

# ============ START SessionContext is_active Tests ===============
def test_is_active_false_when_no_publisher(dummy_executor_config):
    ctx = SessionContext(
        session_id="r",
        publisher=None,
        executor_config=dummy_executor_config,
    )
    assert ctx.is_active is False

def test_is_active_false_when_publisher_not_running(dummy_executor_config):
    pub = DummyPublisher(running=False)
    ctx = SessionContext(
        session_id="r",
        publisher=pub,
        executor_config=dummy_executor_config,
    )
    assert ctx.is_active is False
# ============ END SessionContext is_active Tests ===============

# ============ START SessionContext with_scope_pushed Tests ===============
def test_with_scope_pushed_creates_new_context_and_preserves_lineage(dummy_executor_config):
    pub = DummyPublisher()
    ctx = SessionContext(
        session_id="r",
        publisher=pub,
        executor_config=dummy_executor_config,
    )
    new_ctx = ctx.with_scope_pushed(ScopeEntry(ScopeKind.NODE, "node-1"), run_id="node-1")
    assert isinstance(new_ctx, SessionContext)
    assert new_ctx.current_node_id == "node-1"
    assert new_ctx.run_id == "node-1"
    assert new_ctx.publisher is pub
    assert new_ctx.session_id == ctx.session_id
    assert new_ctx.executor_config is ctx.executor_config
    # original context is untouched (immutable push)
    assert ctx.current_node_id is None
    assert ctx.run_id is None


def test_with_scope_pushed_keeps_run_id_when_not_provided(dummy_executor_config):
    ctx = SessionContext(
        session_id="r",
        publisher=None,
        run_id="run-1",
        executor_config=dummy_executor_config,
    )
    new_ctx = ctx.with_scope_pushed(ScopeEntry(ScopeKind.NODE, "node-2"))
    assert new_ctx.run_id == "run-1"


def test_current_node_id_walks_past_middleware_entry(dummy_executor_config):
    ctx = SessionContext(session_id="r", publisher=None, executor_config=dummy_executor_config)
    ctx = ctx.with_scope_pushed(ScopeEntry(ScopeKind.NODE, "node-1"))
    ctx = ctx.with_scope_pushed(ScopeEntry(ScopeKind.MIDDLEWARE, "mw-1", name="guard"))
    assert ctx.current_node_id == "node-1"
    assert ctx.current_middleware_id == "mw-1"


def test_current_node_id_prefers_node_body_over_stale_node(dummy_executor_config):
    ctx = SessionContext(session_id="r", publisher=None, executor_config=dummy_executor_config)
    ctx = ctx.with_scope_pushed(ScopeEntry(ScopeKind.NODE, "node-1"))
    ctx = ctx.with_scope_pushed(ScopeEntry(ScopeKind.NODE_BODY, "node-1"))
    assert ctx.current_node_id == "node-1"
# ============ END SessionContext with_scope_pushed Tests ===============
