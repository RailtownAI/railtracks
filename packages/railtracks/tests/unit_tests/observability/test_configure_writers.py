from __future__ import annotations

from railtracks.observability import (
    SCOPE_SESSION,
    Event,
    Writer,
    configure,
    configure_writers,
    publish_event,
)


class _FakeWriter:
    """Minimal Writer-protocol stub that records what reaches it."""

    def __init__(self) -> None:
        self.events: list[Event] = []
        self.shutdowns = 0

    def start(self) -> None:
        pass

    def write(self, event: Event) -> None:
        self.events.append(event)

    def shutdown(self) -> None:
        self.shutdowns += 1


def _event() -> Event:
    return Event(event_type="test.event", scope_type=SCOPE_SESSION, scope_id="s1")


def test_records_writers():
    writer: Writer = _FakeWriter()
    configure_writers([writer])
    assert configure.observer._pending == [writer]


def test_empty_writers():
    configure_writers([])
    assert configure.observer._pending == []


def test_second_call_replaces_first():
    a: Writer = _FakeWriter()
    b: Writer = _FakeWriter()
    configure_writers([a])
    configure_writers([b])
    assert configure.observer._pending == [b]


def test_replacing_writers_after_the_first_event_shuts_down_the_old_ones():
    old, new = _FakeWriter(), _FakeWriter()
    configure_writers([old])
    publish_event(_event())

    configure_writers([new])
    publish_event(_event())

    assert len(old.events) == 1
    assert old.shutdowns == 1
    assert len(new.events) == 1
    assert new.shutdowns == 0


def test_reset_swaps_in_fresh_observer():
    configure_writers([_FakeWriter()])
    publish_event(_event())
    first_observer = configure.observer
    configure.reset_for_tests()
    assert configure.observer is not first_observer
    assert configure.observer._pending == []
    assert configure.observer._started is False
