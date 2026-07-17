from __future__ import annotations

import asyncio
import logging
from typing import Any

from railtracks.observability import (
    SCOPE_SESSION,
    Event,
    configure,
    configure_writers,
    publish,
    publish_event,
)


class _CollectingWriter:
    """Writer that keeps every event it sees, for assertions."""

    def __init__(self) -> None:
        self.events: list[Event] = []

    async def start(self) -> None:
        pass

    async def write(self, event: Event) -> None:
        self.events.append(event)

    async def shutdown(self) -> None:
        pass


class _RaisingWriter:
    """Writer whose write() always raises. Used to verify Observer's per-writer
    isolation carries over to publish_event."""

    async def start(self) -> None:
        pass

    async def write(self, event: Event) -> None:
        raise RuntimeError("intentional test failure")

    async def shutdown(self) -> None:
        pass


async def _drain_and_shutdown() -> None:
    """Await scheduled publish tasks, then shutdown the observer so per-writer
    queues drain into writers before assertions."""
    if publish._pending_tasks:
        await asyncio.gather(
            *list(publish._pending_tasks), return_exceptions=True
        )
    if configure._started:
        await configure._observer.shutdown()


def _make_session_event(event_type: str = "test.event", payload: dict[str, Any] | None = None) -> Event:
    return Event(
        event_type=event_type,
        scope_type=SCOPE_SESSION,
        scope_id="test-session",
        payload=payload or {},
    )


def test_no_running_loop_warns_and_drops(caplog):
    with caplog.at_level(logging.WARNING, logger="railtracks.observability.publish"):
        publish_event(_make_session_event())
    assert "no running loop" in caplog.text
    assert publish._pending_tasks == set()


async def test_publishes_to_configured_writer():
    writer = _CollectingWriter()
    configure_writers([writer])

    event = _make_session_event("node.create", {"node_id": "n1"})
    publish_event(event)
    await _drain_and_shutdown()

    assert writer.events == [event]


async def test_no_writers_configured_is_a_silent_no_op():
    # No configure_writers() call at all.
    publish_event(_make_session_event())
    await _drain_and_shutdown()
    # Nothing to assert on the writer side — the point is that this doesn't blow up.
    # The observer started, has zero writers, fan-out is a no-op.
    assert configure._started is True


async def test_writer_that_raises_does_not_break_other_writers():
    good = _CollectingWriter()
    configure_writers([_RaisingWriter(), good])

    event = _make_session_event()
    publish_event(event)
    await _drain_and_shutdown()

    # The raising writer's exception was swallowed by Observer's consumer loop.
    # The good writer still received the event.
    assert good.events == [event]


async def test_multiple_events_delivered_in_order():
    writer = _CollectingWriter()
    configure_writers([writer])

    events = [_make_session_event(f"event-{i}") for i in range(5)]
    for event in events:
        publish_event(event)
    await _drain_and_shutdown()

    assert [e.event_type for e in writer.events] == [e.event_type for e in events]


async def test_publish_event_returns_immediately():
    """publish_event should schedule a task and return without awaiting it."""
    writer = _CollectingWriter()
    configure_writers([writer])

    publish_event(_make_session_event())
    # Right after the call, the task exists but hasn't necessarily run.
    assert len(publish._pending_tasks) == 1

    await _drain_and_shutdown()
    # After the task completes, done_callback removes it from the set.
    assert publish._pending_tasks == set()


async def test_publish_after_shutdown_logs_and_does_not_raise(caplog):
    """If the observer's already shut down, the fire-and-forget task's failure
    is logged, not propagated."""
    writer = _CollectingWriter()
    configure_writers([writer])

    # Start the observer then shut it down, so the NEXT publish's
    # observer.publish() call raises RuntimeError (observer not running).
    await configure._ensure_started()
    await configure._observer.shutdown()

    with caplog.at_level(logging.WARNING, logger="railtracks.observability.publish"):
        publish_event(_make_session_event())
        if publish._pending_tasks:
            await asyncio.gather(
                *list(publish._pending_tasks), return_exceptions=True
            )

    assert "publish_event failed" in caplog.text
