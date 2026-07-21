from __future__ import annotations

import pytest

from railtracks.observability import Event, Writer, configure, configure_writers


class _FakeWriter:
    """Minimal Writer-protocol-satisfying stub for state tests."""

    async def start(self) -> None:
        pass

    async def write(self, event: Event) -> None:
        pass

    async def shutdown(self) -> None:
        pass


def test_records_writers():
    writer: Writer = _FakeWriter()
    configure_writers([writer])
    assert configure.observer._pending_writers == [writer]


def test_empty_writers():
    configure_writers([])
    assert configure.observer._pending_writers == []


def test_second_call_replaces_first():
    a: Writer = _FakeWriter()
    b: Writer = _FakeWriter()
    configure_writers([a])
    configure_writers([b])
    assert configure.observer._pending_writers == [b]


def test_raises_after_observer_started():
    configure.observer._running = True  # simulate start() already ran
    with pytest.raises(RuntimeError, match="configure_writers must be called before"):
        configure_writers([_FakeWriter()])


def test_reset_swaps_in_fresh_observer():
    configure_writers([_FakeWriter()])
    first_observer = configure.observer
    configure.observer._running = True
    configure.reset_for_tests()
    assert configure.observer is not first_observer
    assert configure.observer._pending_writers == []
    assert configure.observer._running is False
