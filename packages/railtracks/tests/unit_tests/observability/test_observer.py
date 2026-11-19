import logging
import time
from concurrent.futures import ThreadPoolExecutor
from typing import List

import pytest
from railtracks.observability import (
    SCOPE_SESSION,
    Event,
    Observer,
    Timestamp,
)
from railtracks.observability import observer as observer_module


class MemoryWriter:
    def __init__(self, raise_on_write: bool = False):
        self.events: List[Event] = []
        self.starts = 0
        self.shutdowns = 0
        self._raise = raise_on_write

    def start(self) -> None:
        self.starts += 1

    def write(self, event: Event) -> None:
        if self._raise:
            raise RuntimeError("boom")
        self.events.append(event)

    def shutdown(self) -> None:
        self.shutdowns += 1


class _RaisingStartWriter:
    def start(self) -> None:
        raise OSError(30, "Read-only file system")

    def write(self, event: Event) -> None:  # pragma: no cover
        raise AssertionError("write() should not be reached")

    def shutdown(self) -> None:  # pragma: no cover
        raise AssertionError("shutdown() should not be reached")


def _event(scope_id: str = "s1", event_type: str = "test") -> Event:
    return Event(
        event_type=event_type,
        stamp=Timestamp.now(),
        scope_type=SCOPE_SESSION,
        scope_id=scope_id,
    )


@pytest.fixture
def warnings_logged(caplog):
    caplog.set_level(logging.WARNING, logger=observer_module.logger.name)
    return caplog


def test_fan_out_to_multiple_writers_before_publish_returns():
    a, b = MemoryWriter(), MemoryWriter()
    obs = Observer()
    obs.configure_writers([a, b])
    obs.publish(_event("e1"))
    assert [e.scope_id for e in a.events] == ["e1"]
    obs.publish(_event("e2"))
    assert [e.scope_id for e in a.events] == ["e1", "e2"]
    assert [e.scope_id for e in b.events] == ["e1", "e2"]


def test_writers_start_on_the_first_event_and_shut_down_once():
    w = MemoryWriter()
    obs = Observer()
    obs.configure_writers([w])
    assert w.starts == 0

    obs.publish(_event())
    obs.publish(_event())
    assert w.starts == 1

    obs.shutdown()
    obs.shutdown()
    assert w.shutdowns == 1


def test_publish_after_shutdown_is_ignored():
    w = MemoryWriter()
    obs = Observer()
    obs.configure_writers([w])
    obs.publish(_event("before"))
    obs.shutdown()
    obs.publish(_event("after"))
    assert [e.scope_id for e in w.events] == ["before"]


def test_default_writers_are_used_only_when_none_are_configured():
    default = MemoryWriter()
    obs = Observer(default_writers=lambda: [default])
    obs.publish(_event())
    assert len(default.events) == 1

    mine = MemoryWriter()
    configured = Observer(default_writers=lambda: [default])
    configured.configure_writers([mine])
    configured.publish(_event())
    assert len(mine.events) == 1
    assert len(default.events) == 1


def test_is_observing_needs_a_writer_and_an_open_observer():
    assert Observer().is_observing is False

    obs = Observer()
    obs.configure_writers([MemoryWriter()])
    assert obs.is_observing is True

    obs.shutdown()
    assert obs.is_observing is False


def test_listeners_run_before_writers():
    order: list[str] = []

    class _OrderWriter(MemoryWriter):
        def write(self, event: Event) -> None:
            order.append("writer")

    obs = Observer()
    obs.configure_writers([_OrderWriter()])
    obs.add_listener(lambda event: order.append("listener"))
    obs.publish(_event())
    assert order == ["listener", "writer"]


def test_add_listener_is_idempotent():
    obs = Observer()
    calls: list[Event] = []
    assert obs.add_listener(calls.append) is True
    assert obs.add_listener(calls.append) is False
    obs.publish(_event())
    assert len(calls) == 1


def test_writer_exception_does_not_affect_other_writers():
    bad = MemoryWriter(raise_on_write=True)
    good = MemoryWriter()
    obs = Observer()
    obs.configure_writers([bad, good])
    obs.publish(_event("e1"))
    obs.publish(_event("e2"))
    obs.shutdown()
    assert [e.scope_id for e in good.events] == ["e1", "e2"]
    assert bad.shutdowns == 1


def test_a_writer_is_never_called_from_two_threads_at_once():
    class _OverlapWriter(MemoryWriter):
        def __init__(self) -> None:
            super().__init__()
            self.inside = 0
            self.overlaps = 0

        def write(self, event: Event) -> None:
            self.inside += 1
            if self.inside > 1:
                self.overlaps += 1
            time.sleep(0.0005)
            self.events.append(event)
            self.inside -= 1

    w = _OverlapWriter()
    obs = Observer()
    obs.configure_writers([w])

    def publish_some() -> None:
        for _ in range(20):
            obs.publish(_event())

    with ThreadPoolExecutor(max_workers=4) as pool:
        for future in [pool.submit(publish_some) for _ in range(4)]:
            future.result()

    assert len(w.events) == 80
    assert w.overlaps == 0


def test_configure_writers_after_the_first_event_swaps_them():
    old, new = MemoryWriter(), MemoryWriter()
    obs = Observer()
    obs.configure_writers([old])
    obs.publish(_event("e1"))

    obs.configure_writers([new])
    obs.publish(_event("e2"))

    assert [e.scope_id for e in old.events] == ["e1"]
    assert old.shutdowns == 1
    assert [e.scope_id for e in new.events] == ["e2"]
    assert new.starts == 1


def test_a_writer_whose_start_fails_is_skipped(warnings_logged):
    good = MemoryWriter()
    obs = Observer()
    obs.configure_writers([_RaisingStartWriter(), good])
    obs.publish(_event())

    assert [sink.name for sink in obs._writers] == ["writer-1"]
    assert len(good.events) == 1
    assert any("failed to start" in r.getMessage() for r in warnings_logged.records)
