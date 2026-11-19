from __future__ import annotations

import asyncio
from typing import Any

from railtracks.observability import (
    SCOPE_SESSION,
    Event,
    configure,
    configure_writers,
    publish_event,
    shutdown,
)
from railtracks.observability.writers.jsonl import JsonlWriter


class _CollectingWriter:
    """Writer that keeps every event it sees, for assertions."""

    def __init__(self) -> None:
        self.events: list[Event] = []

    def start(self) -> None:
        pass

    def write(self, event: Event) -> None:
        self.events.append(event)

    def shutdown(self) -> None:
        pass


class _RaisingWriter:
    """Writer whose write() always raises. Verifies Observer's per-writer
    isolation carries over through publish_event."""

    def start(self) -> None:
        pass

    def write(self, event: Event) -> None:
        raise RuntimeError("intentional test failure")

    def shutdown(self) -> None:
        pass


def _make_session_event(
    event_type: str = "test.event", payload: dict[str, Any] | None = None
) -> Event:
    return Event(
        event_type=event_type,
        scope_type=SCOPE_SESSION,
        scope_id="test-session",
        payload=payload or {},
    )


def test_publishes_to_configured_writer_before_returning():
    writer = _CollectingWriter()
    configure_writers([writer])

    event = _make_session_event("node.create", {"node_id": "n1"})
    publish_event(event)

    assert writer.events == [event]


def test_no_writers_configured_is_a_silent_no_op():
    publish_event(_make_session_event())
    assert configure.observer.is_observing is False


def test_writer_that_raises_does_not_break_other_writers():
    good = _CollectingWriter()
    configure_writers([_RaisingWriter(), good])

    event = _make_session_event()
    publish_event(event)

    assert good.events == [event]


def test_multiple_events_delivered_in_order():
    writer = _CollectingWriter()
    configure_writers([writer])

    events = [_make_session_event(f"event-{i}") for i in range(5)]
    for event in events:
        publish_event(event)

    assert [e.event_type for e in writer.events] == [e.event_type for e in events]


def test_publish_after_shutdown_is_ignored():
    writer = _CollectingWriter()
    configure_writers([writer])
    publish_event(_make_session_event("first"))
    shutdown()

    publish_event(_make_session_event("second"))

    assert [e.event_type for e in writer.events] == ["first"]


def test_events_disabled_starts_no_default_writer():
    """RAILTRACKS_DISABLE_EVENTS=True is set by the root conftest."""
    publish_event(_make_session_event())
    assert configure.observer._writers == ()


def test_default_writer_is_a_jsonl_writer_when_events_are_enabled(
    monkeypatch, tmp_path
):
    monkeypatch.delenv("RAILTRACKS_DISABLE_EVENTS", raising=False)
    monkeypatch.setenv("RAILTRACKS_EVENTS_DIR", str(tmp_path / "events"))

    publish_event(_make_session_event())

    sinks = configure.observer._writers
    assert len(sinks) == 1
    assert isinstance(sinks[0].writer, JsonlWriter)
    assert (tmp_path / "events" / "test-session.jsonl").exists()
    shutdown()


def test_explicit_configure_writers_wins_over_the_default(monkeypatch):
    monkeypatch.delenv("RAILTRACKS_DISABLE_EVENTS", raising=False)
    user_writer = _CollectingWriter()
    configure_writers([user_writer])

    publish_event(_make_session_event())

    assert [sink.writer for sink in configure.observer._writers] == [user_writer]


async def test_publish_from_a_worker_thread_delivers_in_order():
    writer = _CollectingWriter()
    configure_writers([writer])

    def record_off_loop():
        for i in range(5):
            publish_event(_make_session_event(f"sync.{i}"))

    await asyncio.to_thread(record_off_loop)

    assert [e.event_type for e in writer.events] == [f"sync.{i}" for i in range(5)]


def test_publish_from_a_thread_with_no_event_loop_delivers():
    writer = _CollectingWriter()
    configure_writers([writer])

    publish_event(_make_session_event("no.loop"))

    assert [e.event_type for e in writer.events] == ["no.loop"]
