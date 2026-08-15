"""Direct unit tests for `events/send.py`'s parent-resolution logic.

`pipe()` -> `event.resolve_relationships()` -> each event family's own
`_get_spatial_parent`/`_get_parent` (see `events/_resolve.py`) is the piece of
the observability system that decides where a middleware/LLM event sits in
the call graph: its `spatial_parent` (a node, an LLM call, or nothing) and its
`parent` (the middleware/LLM invocation that owns it). It reads off the
contextvars-backed scope stack in `context/central.py` /
`context/session_context.py`.

These tests drive the real `ContextVarScopeManager` (not mocks) to push actual
scope stacks, then inspect the resolved `spatial_parent`/`parent` on the event
object after `pipe()` mutates it in place. This is the only place these fields
are exercised directly -- integration tests only see the effect indirectly.
`events/_resolve.py`'s resolver functions get more exhaustive, synthetic-chain
coverage in `test_resolve.py`.
"""

from __future__ import annotations

from contextlib import ExitStack

import pytest
import railtracks.context.central as central
from railtracks.context.central import ContextVarScopeManager
from railtracks.events._base import (
    LLMAndMiddlewareSpatialParent,
    NodeAndMiddlewareSpatialParent,
    NodeSpatialParent,
    NoSpatialParent,
)
from railtracks.events.llm import LLMCreationEvent, LLMInvocationEvent, LLMParent
from railtracks.events.middleware import (
    MiddlewareCreationEvent,
    MiddlewareInvocationEvent,
    MiddlewareParent,
)
from railtracks.events.send import pipe
from railtracks.llm.history import MessageHistory
from railtracks.llm.providers import ModelProvider
from railtracks.observability import configure
from railtracks.utils.config import ExecutorConfig


@pytest.fixture(autouse=True)
def _clean_state():
    """Every test gets a fresh scope + a started (zero-writer) observer.

    `pipe()` always calls through to `publish_event`, which raises unless the
    process-wide Observer singleton has been started -- see
    `observability/observer.py::Observer.publish`. Zero writers is enough;
    we only care about the mutation `_resolve_parent` performs on the event.
    """
    central.delete_globals()
    configure.reset_for_tests()
    yield
    central.delete_globals()
    configure.reset_for_tests()


def _register(session_id: str = "s1") -> None:
    central.register_globals(
        session_id=session_id,
        rt_publisher=None,
        executor_config=ExecutorConfig(),
        global_context_vars={},
    )


async def _pipe(event):
    """Start the observer (idempotent, zero writers) and pipe `event`."""
    await configure.ensure_started()
    await pipe(event)
    return event


# ---------------------------------------------------------------------------
# Middleware events under a node
# ---------------------------------------------------------------------------


async def test_middleware_event_under_node_only_resolves_node_spatial_parent():
    _register()
    mgr = ContextVarScopeManager()

    with mgr.enter_node("node-1"):
        with mgr.enter_middleware("mw-A") as call_id:
            event = await _pipe(MiddlewareInvocationEvent(args=(), kwargs={}))

    assert event.spatial_parent == NodeAndMiddlewareSpatialParent(
        node_id="node-1", middleware_invoke_id=None
    )
    assert event.parent == MiddlewareParent(
        middleware_type_id="mw-A", middleware_invoke_id=call_id
    )


async def test_nested_middleware_event_records_enclosing_middleware_invoke_id():
    """Node -> mw-A -> mw-B (nested): B's spatial parent records A's *invoke* id."""
    _register()
    mgr = ContextVarScopeManager()

    with mgr.enter_node("node-1"):
        with mgr.enter_middleware("mw-A") as a_call_id:
            with mgr.enter_middleware("mw-B") as b_call_id:
                event = await _pipe(MiddlewareInvocationEvent(args=(), kwargs={}))

    assert event.spatial_parent == NodeAndMiddlewareSpatialParent(
        node_id="node-1", middleware_invoke_id=a_call_id
    )
    assert event.parent == MiddlewareParent(
        middleware_type_id="mw-B", middleware_invoke_id=b_call_id
    )


# ---------------------------------------------------------------------------
# Middleware events under an LLM call (model-level middleware / guards)
# ---------------------------------------------------------------------------


async def test_middleware_event_under_llm_scope_resolves_llm_spatial_parent():
    """Model-level middleware (guards, before_llm/wrap_llm) sits *inside* the LLM
    scope -- see `ModelInvoker.invoke`, which enters `enter_llm_call` before
    running its middleware chain. Its events must resolve
    `LLMAndMiddlewareSpatialParent`, never `NodeSpatialParent`, even though a
    node is further up the stack.
    """
    _register()
    mgr = ContextVarScopeManager()

    with mgr.enter_node("node-1"):
        with mgr.enter_llm_call("model-x"):
            llm_call_data = central.get_llm_call_id()
            with mgr.enter_middleware("guard-A") as call_id:
                event = await _pipe(MiddlewareInvocationEvent(args=(), kwargs={}))

    assert event.spatial_parent == LLMAndMiddlewareSpatialParent(
        llm_invoke_id=llm_call_data.call_id, middleware_invoke_id=None
    )
    assert event.parent == MiddlewareParent(
        middleware_type_id="guard-A", middleware_invoke_id=call_id
    )


async def test_nested_model_middleware_under_llm_scope_records_enclosing_invoke_id():
    _register()
    mgr = ContextVarScopeManager()

    with mgr.enter_node("node-1"):
        with mgr.enter_llm_call("model-x"):
            llm_call_data = central.get_llm_call_id()
            with mgr.enter_middleware("guard-A") as a_call_id:
                with mgr.enter_middleware("guard-B") as b_call_id:
                    event = await _pipe(MiddlewareInvocationEvent(args=(), kwargs={}))

    assert event.spatial_parent == LLMAndMiddlewareSpatialParent(
        llm_invoke_id=llm_call_data.call_id, middleware_invoke_id=a_call_id
    )
    assert event.parent == MiddlewareParent(
        middleware_type_id="guard-B", middleware_invoke_id=b_call_id
    )


async def test_parent_middleware_does_not_cross_the_llm_boundary():
    """Node -> node-mw-A -> LLM -> model-mw-B: B's spatial parent records NO
    enclosing middleware, even though node-mw-A is further up the stack.

    `SessionContext.parent_middleware_id` only looks one scope-stack level up
    (the entry directly enclosing the current one) -- it never walks past an
    LLM (or node) entry to find an outer middleware. This is the sharpest
    footgun in the whole design: pinned explicitly so a "helpful" refactor to
    walk further up doesn't silently change semantics unnoticed.
    """
    _register()
    mgr = ContextVarScopeManager()

    with mgr.enter_node("node-1"):
        with mgr.enter_middleware("node-mw-A"):
            with mgr.enter_llm_call("model-x"):
                llm_call_data = central.get_llm_call_id()
                with mgr.enter_middleware("model-mw-B") as b_call_id:
                    event = await _pipe(MiddlewareInvocationEvent(args=(), kwargs={}))

    assert event.spatial_parent == LLMAndMiddlewareSpatialParent(
        llm_invoke_id=llm_call_data.call_id, middleware_invoke_id=None
    )
    assert event.parent == MiddlewareParent(
        middleware_type_id="model-mw-B", middleware_invoke_id=b_call_id
    )


# ---------------------------------------------------------------------------
# LLM message events (the terminal llm.invocation/response/failure family)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("middleware_depth", [0, 1, 2])
async def test_llm_message_event_always_resolves_to_nearest_node(middleware_depth):
    """llm.invocation/response/failure are always spatially anchored to the
    nearest *node*, skipping past the LLM scope and any nested model
    middleware -- regardless of how many middleware layers sit in between.
    Their `parent` (which specific LLM call) is a separate, distinct field.
    """
    _register()
    mgr = ContextVarScopeManager()

    with ExitStack() as stack:
        stack.enter_context(mgr.enter_node("node-1"))
        stack.enter_context(mgr.enter_llm_call("model-x"))
        for i in range(middleware_depth):
            stack.enter_context(mgr.enter_middleware(f"mw-{i}"))

        llm_call_data = central.get_llm_call_id()
        event = await _pipe(LLMInvocationEvent(message_input=MessageHistory([])))

    assert event.spatial_parent == NodeSpatialParent(node_id="node-1")
    assert event.parent == LLMParent(
        llm_invoke_id=llm_call_data.call_id, llm_type_id=llm_call_data.type_id
    )


# ---------------------------------------------------------------------------
# Creation events: always NoSpatialParent, never require an active scope
# ---------------------------------------------------------------------------


async def test_creation_events_have_no_spatial_parent_and_need_no_active_scope():
    _register()  # session registered, but no node/middleware/LLM scope pushed

    mw_event = await _pipe(
        MiddlewareCreationEvent(middleware_type_id="mw-A", middleware_name="A")
    )
    assert mw_event.spatial_parent == NoSpatialParent()

    llm_event = await _pipe(
        LLMCreationEvent(
            llm_id="model-x",
            model_provider=ModelProvider.OPENAI,
            model_name="gpt-x",
        )
    )
    assert llm_event.spatial_parent == NoSpatialParent()


# ---------------------------------------------------------------------------
# Missing-context assertions: defensive checks that a resolver never
# silently invents a parent when the required scope isn't active.
# ---------------------------------------------------------------------------


async def test_middleware_event_with_no_node_or_llm_context_raises():
    _register()
    event = MiddlewareInvocationEvent(args=(), kwargs={})

    with pytest.raises(AssertionError, match="Expected a scope chain"):
        await _pipe(event)


async def test_middleware_event_without_active_middleware_scope_raises():
    _register()
    mgr = ContextVarScopeManager()

    with mgr.enter_node("node-1"):
        event = MiddlewareInvocationEvent(args=(), kwargs={})
        with pytest.raises(AssertionError, match="Expected a scope chain"):
            await _pipe(event)


async def test_llm_message_event_without_active_llm_call_scope_raises():
    _register()
    mgr = ContextVarScopeManager()

    with mgr.enter_node("node-1"):
        event = LLMInvocationEvent(message_input=MessageHistory([]))
        with pytest.raises(AssertionError, match="Expected an LLM scope entry"):
            await _pipe(event)


async def test_llm_message_event_without_active_node_scope_raises():
    _register()
    mgr = ContextVarScopeManager()

    with mgr.enter_llm_call("model-x"):
        event = LLMInvocationEvent(message_input=MessageHistory([]))
        with pytest.raises(AssertionError, match="Expected a node scope entry"):
            await _pipe(event)
