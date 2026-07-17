from __future__ import annotations

import pytest

from railtracks.observability import Event, Writer, configure_writers, configure


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
    assert configure._pending_writers == [writer]


def test_empty_writers():
    configure_writers([])
    assert configure._pending_writers == []


def test_second_call_replaces_first():
    a: Writer = _FakeWriter()
    b: Writer = _FakeWriter()
    configure_writers([a])
    configure_writers([b])
    assert configure._pending_writers == [b]


def test_raises_after_observer_started():
    configure._started = True  # simulate _ensure_started already ran
    with pytest.raises(RuntimeError, match="configure_writers must be called before"):
        configure_writers([_FakeWriter()])


def test_reset_clears_state():
    configure_writers([_FakeWriter()])
    configure._started = True
    configure._reset_for_tests()
    assert configure._pending_writers == []
    assert configure._started is False
