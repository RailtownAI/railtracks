from __future__ import annotations

from typing import Any

import pytest

from railtracks.observability import (
    SCOPE_SESSION,
    Event,
    configure,
    configure_writers,
    ensure_started,
    publish_event,
    shutdown,
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
    """Writer whose write() always raises. Verifies Observer's per-writer
    isolation carries over through publish_event."""

    async def start(self) -> None:
        pass

    async def write(self, event: Event) -> None:
        raise RuntimeError("intentional test failure")

    async def shutdown(self) -> None:
        pass


def _make_session_event(event_type: str = "test.event", payload: dict[str, Any] | None = None) -> Event:
    return Event(
        event_type=event_type,
        scope_type=SCOPE_SESSION,
        scope_id="test-session",
        payload=payload or {},
    )


async def test_publish_before_start_raises():
    """publish_event without a prior ensure_started() propagates the
    Observer's RuntimeError. Callers get a loud failure, not a silent drop."""
    configure_writers([_CollectingWriter()])
    with pytest.raises(RuntimeError, match="Observer is not running"):
        await publish_event(_make_session_event())


async def test_publishes_to_configured_writer():
    writer = _CollectingWriter()
    configure_writers([writer])
    await ensure_started()

    event = _make_session_event("node.create", {"node_id": "n1"})
    await publish_event(event)
    await shutdown()  # drains queues into writers

    assert writer.events == [event]


async def test_no_writers_configured_is_a_silent_no_op():
    # No configure_writers() call at all.
    await ensure_started()
    await publish_event(_make_session_event())  # zero writers → fan-out is a no-op
    await shutdown()


async def test_writer_that_raises_does_not_break_other_writers():
    good = _CollectingWriter()
    configure_writers([_RaisingWriter(), good])
    await ensure_started()

    event = _make_session_event()
    await publish_event(event)
    await shutdown()

    # The raising writer's exception was swallowed by Observer's consumer loop.
    # The good writer still received the event.
    assert good.events == [event]


async def test_multiple_events_delivered_in_order():
    """Deterministic ordering: successive publish_event calls fan out to the
    writer's queue in call order."""
    writer = _CollectingWriter()
    configure_writers([writer])
    await ensure_started()

    events = [_make_session_event(f"event-{i}") for i in range(5)]
    for event in events:
        await publish_event(event)
    await shutdown()

    assert [e.event_type for e in writer.events] == [e.event_type for e in events]


async def test_publish_after_shutdown_raises():
    """After shutdown, publish_event propagates RuntimeError. Same loud
    failure as publish-before-start."""
    writer = _CollectingWriter()
    configure_writers([writer])
    await ensure_started()
    await publish_event(_make_session_event("first"))
    await shutdown()

    with pytest.raises(RuntimeError, match="Observer is not running"):
        await publish_event(_make_session_event("second"))
    # Only the pre-shutdown event landed.
    assert [e.event_type for e in writer.events] == ["first"]


async def test_ensure_started_before_configure_writers_starts_with_no_writers(caplog):
    """Calling ensure_started() with no prior configure_writers() is fine —
    the observer starts with zero pending writers. Subsequent publishes just
    fan out to nothing."""
    await ensure_started()
    assert configure.observer._running is True
    await publish_event(_make_session_event())
    await shutdown()
