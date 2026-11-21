from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor

from railtracks.observability import (
    SCOPE_SESSION,
    Event,
    configure,
    configure_writers,
    publish_event,
    shutdown,
)


class _CollectingWriter:
    def __init__(self) -> None:
        self.events: list[Event] = []
        self.starts = 0
        self.shutdowns = 0

    def start(self) -> None:
        self.starts += 1

    def write(self, event: Event) -> None:
        self.events.append(event)

    def shutdown(self) -> None:
        self.shutdowns += 1


def _make_session_event(event_type: str = "test.event") -> Event:
    return Event(
        event_type=event_type,
        scope_type=SCOPE_SESSION,
        scope_id="s1",
        payload={},
    )


def test_first_events_from_many_threads_start_the_writers_once():
    writer = _CollectingWriter()
    configure_writers([writer])
    barrier = threading.Barrier(8)

    def publish_some() -> None:
        barrier.wait()
        for _ in range(50):
            publish_event(_make_session_event())

    with ThreadPoolExecutor(max_workers=8) as pool:
        for future in [pool.submit(publish_some) for _ in range(8)]:
            future.result()

    assert writer.starts == 1
    assert len(writer.events) == 400


def test_shutdown_stops_writers_once_and_later_events_are_ignored():
    writer = _CollectingWriter()
    configure_writers([writer])
    publish_event(_make_session_event("before"))

    shutdown()
    shutdown()
    publish_event(_make_session_event("after"))

    assert writer.shutdowns == 1
    assert [e.event_type for e in writer.events] == ["before"]


def test_reset_for_tests_swaps_in_fresh_observer():
    writer1 = _CollectingWriter()
    configure_writers([writer1])
    event1 = _make_session_event("first")
    publish_event(event1)
    assert writer1.events == [event1]

    first_observer = configure.observer

    configure.reset_for_tests()
    assert configure.observer is not first_observer
    assert configure.observer._started is False
    assert configure.observer._pending == []

    writer2 = _CollectingWriter()
    configure_writers([writer2])
    event2 = _make_session_event("second")
    publish_event(event2)
    assert writer2.events == [event2]
    assert writer1.events == [event1]
