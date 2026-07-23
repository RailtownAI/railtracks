from __future__ import annotations

import asyncio
import concurrent.futures
import contextvars
from datetime import datetime, timezone
from typing import Any, Callable, TypeVar

import pytest
from railtracks.context.central import register_globals, runner_context
from railtracks.exceptions import ContextError
from railtracks.observability import SCOPE_SESSION, Event
from railtracks.observability_bridge import make_session_event
from railtracks.utils.config import ExecutorConfig

T = TypeVar("T")


def _run_in_session(session_id: str, fn: Callable[[], T]) -> T:
    """Run `fn` inside a fresh contextvars.Context with runner_context set.
    Isolates contextvar changes from other tests."""
    def _body() -> T:
        register_globals(
            session_id=session_id,
            rt_publisher=None,
            parent_id=None,
            executor_config=ExecutorConfig(),
            global_context_vars={},
        )
        return fn()

    return contextvars.Context().run(_body)


def test_raises_outside_session():
    def _body():
        make_session_event("test.event", {"k": "v"})

    with pytest.raises(ContextError):
        contextvars.Context().run(_body)


def test_returns_event_inside_session():
    event = _run_in_session(
        "session-abc",
        lambda: make_session_event("node.create", {"node_id": "n1"}),
    )
    assert isinstance(event, Event)
    assert event.event_type == "node.create"
    assert event.scope_type == SCOPE_SESSION
    assert event.scope_id == "session-abc"


def test_payload_stored_as_is():
    payload: dict[str, Any] = {"a": 1, "b": [1, 2, 3], "c": {"nested": True}}
    event = _run_in_session("s1", lambda: make_session_event("test.event", payload))
    assert event.payload == payload


def test_stamp_is_tz_aware_utc():
    before = datetime.now(timezone.utc)
    event = _run_in_session("s1", lambda: make_session_event("x", {}))
    after = datetime.now(timezone.utc)

    assert event.stamp.tzinfo is not None
    assert event.stamp.utcoffset() == timezone.utc.utcoffset(event.stamp)
    assert before <= event.stamp <= after


def test_event_type_is_free_form():
    event = _run_in_session(
        "s1", lambda: make_session_event("totally.made.up.event.name", {})
    )
    assert event.event_type == "totally.made.up.event.name"


def test_scope_id_propagates_across_copy_context_boundary():
    """Regression for orchestration/flow.py:151.

    That branch runs `ctx.run(asyncio.run, coro)` inside a ThreadPoolExecutor.
    Any code inside the coroutine that reads a ContextVar must see the outer
    context's value. If contextvar propagation ever breaks there, this test
    catches it — make_session_event would raise ContextError, or return the wrong scope.
    """
    captured: list[Event] = []

    def _outer():
        register_globals(
            session_id="propagated-session-xyz",
            rt_publisher=None,
            parent_id=None,
            executor_config=ExecutorConfig(),
            global_context_vars={},
        )

        # Mirror flow.py:151 exactly.
        ctx = contextvars.copy_context()

        async def _inner():
            return make_session_event("test.event", {"marker": "in-inner"})

        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(ctx.run, asyncio.run, _inner())
            event = future.result()

        captured.append(event)

    contextvars.Context().run(_outer)

    assert captured[0].scope_id == "propagated-session-xyz"
    assert captured[0].event_type == "test.event"
    assert captured[0].payload == {"marker": "in-inner"}


def test_leaves_runner_context_none_outside_helper():
    """Sanity check that _run_in_session doesn't leak state into other tests."""
    _run_in_session("leaky-session", lambda: make_session_event("x", {}))
    assert runner_context.get() is None
