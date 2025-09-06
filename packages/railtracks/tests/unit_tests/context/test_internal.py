
import pytest
from unittest import mock
from railtracks.context.internal import InternalContext

# ============ START DummyPublisher Helper ===============
class DummyPublisher:
    def __init__(self, running=True):
        self._running = running
    def is_running(self):
        return self._running
# ============ END DummyPublisher Helper ===============

# ============ START InternalContext Property Tests ===============
def test_internal_context_properties(dummy_executor_config):
    pub = DummyPublisher()
    ctx = InternalContext(
        session_id="runner-1",
        publisher=pub,
        parent_id="parent-1",
        executor_config=dummy_executor_config,
    )
    assert ctx.session_id == "runner-1"
    assert ctx.parent_id == "parent-1"
    assert ctx.publisher is pub
    assert ctx.executor_config is dummy_executor_config
    assert ctx.is_active is True
# ============ END InternalContext Property Tests ===============

# ============ START InternalContext Setter Tests ===============
def test_internal_context_setters(dummy_executor_config):
    ctx = InternalContext(
        session_id=None,
        publisher=None,
        parent_id=None,
        executor_config=dummy_executor_config,
    )
    ctx.session_id = "r2"
    ctx.parent_id = "p2"
    pub = DummyPublisher()
    ctx.publisher = pub
    new_config = mock.Mock()
    ctx.executor_config = new_config
    assert ctx.session_id == "r2"
    assert ctx.parent_id == "p2"
    assert ctx.publisher is pub
    assert ctx.executor_config is new_config
# ============ END InternalContext Setter Tests ===============

# ============ START InternalContext is_active Tests ===============
def test_is_active_false_when_no_publisher(dummy_executor_config):
    ctx = InternalContext(
        session_id="r",
        publisher=None,
        parent_id="p",
        executor_config=dummy_executor_config,
    )
    assert ctx.is_active is False

def test_is_active_false_when_publisher_not_running(dummy_executor_config):
    pub = DummyPublisher(running=False)
    ctx = InternalContext(
        session_id="r",
        publisher=pub,
        parent_id="p",
        executor_config=dummy_executor_config,
    )
    assert ctx.is_active is False
# ============ END InternalContext is_active Tests ===============

# ============ START InternalContext prepare_new Tests ===============
def test_prepare_new_creates_new_context(dummy_executor_config):
    pub = DummyPublisher()
    ctx = InternalContext(
        session_id="r",
        publisher=pub,
        parent_id="old-parent",
        executor_config=dummy_executor_config,
    )
    new_ctx = ctx.prepare_new("new-parent")
    assert isinstance(new_ctx, InternalContext)
    assert new_ctx.parent_id == "new-parent"
    assert new_ctx.publisher is pub
    assert new_ctx.session_id == ctx.session_id
    assert new_ctx.executor_config is ctx.executor_config
# ============ END InternalContext prepare_new Tests ===============
