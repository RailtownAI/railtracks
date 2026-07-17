from __future__ import annotations

import pytest

from railtracks.observability import Event, Writer
from railtracks.observability_bridge import _state, configure_writers


class _FakeWriter:
    """Minimal Writer-protocol-satisfying stub for state tests."""

    async def start(self) -> None:
        pass

    async def write(self, event: Event) -> None:
        pass

    async def shutdown(self) -> None:
        pass


def test_records_writers_and_include_default_true():
    writer: Writer = _FakeWriter()
    configure_writers([writer], include_default=True)
    assert _state._pending_writers == [writer]
    assert _state._include_default is True


def test_include_default_false_replaces_default():
    writer: Writer = _FakeWriter()
    configure_writers([writer], include_default=False)
    assert _state._pending_writers == [writer]
    assert _state._include_default is False


def test_empty_writers_with_default_kept():
    configure_writers([], include_default=True)
    assert _state._pending_writers == []
    assert _state._include_default is True


def test_second_call_replaces_first():
    a: Writer = _FakeWriter()
    b: Writer = _FakeWriter()
    configure_writers([a], include_default=False)
    configure_writers([b], include_default=True)
    assert _state._pending_writers == [b]
    assert _state._include_default is True


def test_raises_after_observer_started():
    _state._started = True  # simulate a first publish already happened
    with pytest.raises(RuntimeError, match="configure_writers must be called before"):
        configure_writers([_FakeWriter()])


def test_reset_clears_state():
    configure_writers([_FakeWriter()], include_default=False)
    _state._started = True
    _state._reset_for_tests()
    assert _state._pending_writers == []
    assert _state._include_default is True
    assert _state._started is False


def test_ensure_started_is_stubbed_until_commit_3():
    """Sanity check that Commit 2 doesn't accidentally ship real start logic."""
    import asyncio

    with pytest.raises(NotImplementedError):
        asyncio.run(_state._ensure_started())
