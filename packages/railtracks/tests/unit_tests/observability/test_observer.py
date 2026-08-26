import asyncio
from typing import List

import pytest
from railtracks.observability import (
    SCOPE_SESSION,
    Event,
    Observer,
    QueuePolicy,
    Timestamp,
)


class MemoryWriter:
    def __init__(
        self,
        sleep_before_write: float = 0.0,
        raise_on_write: bool = False,
    ):
        self.events: List[Event] = []
        self.started = False
        self.shutdown_called = False
        self._sleep = sleep_before_write
        self._raise = raise_on_write

    async def start(self) -> None:
        self.started = True

    async def write(self, event: Event) -> None:
        if self._sleep:
            await asyncio.sleep(self._sleep)
        if self._raise:
            raise RuntimeError("boom")
        self.events.append(event)

    async def shutdown(self) -> None:
        self.shutdown_called = True


def _event(scope_id: str = "s1") -> Event:
    return Event(
        event_type="test",
        stamp=Timestamp.now(),
        scope_type=SCOPE_SESSION,
        scope_id=scope_id,
    )


async def test_fan_out_to_multiple_writers():
    a, b = MemoryWriter(), MemoryWriter()
    async with Observer() as obs:
        await obs.register(a, "a")
        await obs.register(b, "b")
        await obs.publish(_event("e1"))
        await obs.publish(_event("e2"))
    assert [e.scope_id for e in a.events] == ["e1", "e2"]
    assert [e.scope_id for e in b.events] == ["e1", "e2"]


async def test_writer_start_and_shutdown_are_called():
    w = MemoryWriter()
    async with Observer() as obs:
        await obs.register(w, "w")
        assert w.started is True
    assert w.shutdown_called is True


async def test_slow_writer_does_not_block_fast_writer():
    slow = MemoryWriter(sleep_before_write=0.05)
    fast = MemoryWriter()
    obs = Observer()
    await obs.start()
    try:
        await obs.register(slow, "slow")
        await obs.register(fast, "fast")
        for i in range(5):
            await obs.publish(_event(f"e{i}"))
        await asyncio.sleep(0.01)
        assert len(fast.events) == 5
        assert len(slow.events) < 5
    finally:
        await obs.shutdown()
    assert len(slow.events) == 5


async def test_writer_exception_does_not_kill_observer():
    bad = MemoryWriter(raise_on_write=True)
    good = MemoryWriter()
    async with Observer() as obs:
        await obs.register(bad, "bad")
        await obs.register(good, "good")
        await obs.publish(_event("e1"))
        await obs.publish(_event("e2"))
    assert [e.scope_id for e in good.events] == ["e1", "e2"]
    assert bad.events == []
    assert bad.shutdown_called is True


async def test_shutdown_drains_pending_events():
    slow = MemoryWriter(sleep_before_write=0.005)
    obs = Observer()
    await obs.start()
    await obs.register(slow, "slow")
    for i in range(5):
        await obs.publish(_event(f"e{i}"))
    await obs.shutdown()
    assert len(slow.events) == 5


async def test_publish_after_shutdown_raises():
    obs = Observer()
    await obs.start()
    await obs.register(MemoryWriter(), "w")
    await obs.shutdown()
    with pytest.raises(RuntimeError):
        await obs.publish(_event())


async def test_register_when_not_running_raises():
    """Public register still requires start() first. Pre-start batch
    registration goes through configure_writers()."""
    obs = Observer()
    with pytest.raises(RuntimeError, match="Observer is not running"):
        await obs.register(MemoryWriter(), "w")


async def test_configure_writers_then_start_registers_pending():
    """The Observer-level batch flow: configure_writers([...]) then start()
    registers each with auto-name writer-{i}."""
    a, b = MemoryWriter(), MemoryWriter()
    obs = Observer()
    obs.configure_writers([a, b])
    try:
        await obs.start()
        # Both writers were started and consumer tasks are running.
        assert a.started is True
        assert b.started is True
        assert set(obs._writers.keys()) == {"writer-0", "writer-1"}
        await obs.publish(_event("e1"))
    finally:
        await obs.shutdown()
    assert [e.scope_id for e in a.events] == ["e1"]
    assert [e.scope_id for e in b.events] == ["e1"]


async def test_configure_writers_after_start_raises():
    obs = Observer()
    await obs.start()
    try:
        with pytest.raises(RuntimeError, match="configure_writers must be called before"):
            obs.configure_writers([MemoryWriter()])
    finally:
        await obs.shutdown()


async def test_concurrent_start_coalesces():
    """Two concurrent Observer.start() calls: only one runs the pending-writer
    registration; the other coalesces on the lock. No duplicate-name errors."""
    a, b = MemoryWriter(), MemoryWriter()
    obs = Observer()
    obs.configure_writers([a, b])
    try:
        await asyncio.gather(*[obs.start() for _ in range(5)])
        assert obs._running is True
        assert set(obs._writers.keys()) == {"writer-0", "writer-1"}
    finally:
        await obs.shutdown()


async def test_register_duplicate_name_raises():
    async with Observer() as obs:
        await obs.register(MemoryWriter(), "same")
        with pytest.raises(ValueError):
            await obs.register(MemoryWriter(), "same")


async def test_unregister_cleans_up_writer_and_stops_delivery():
    a, b = MemoryWriter(), MemoryWriter()
    async with Observer() as obs:
        await obs.register(a, "a")
        await obs.register(b, "b")
        await obs.publish(_event("e1"))
        await obs.unregister("a")
        assert a.shutdown_called is True
        await obs.publish(_event("e2"))
    assert [e.scope_id for e in a.events] == ["e1"]
    assert [e.scope_id for e in b.events] == ["e1", "e2"]


async def test_unregister_unknown_name_raises():
    async with Observer() as obs:
        with pytest.raises(KeyError):
            await obs.unregister("nope")


async def test_drop_oldest_when_queue_full():
    gate = asyncio.Event()

    class GatedWriter:
        async def start(self) -> None:
            return None

        async def write(self, event: Event) -> None:
            await gate.wait()

        async def shutdown(self) -> None:
            return None

    obs = Observer()
    await obs.start()
    try:
        await obs.register(
            GatedWriter(), "gated", maxsize=3, policy=QueuePolicy.DROP_OLDEST
        )
        for i in range(6):
            await obs.publish(_event(f"e{i}"))
        assert obs._drops["gated"] >= 3
    finally:
        gate.set()
        await obs.shutdown()


# ------------------------------------------------------------------------
# Sentinel: distinguishes "configure_writers never called" from "called with []"
# ------------------------------------------------------------------------


def test_has_explicit_writers_false_on_fresh_observer():
    assert Observer().has_explicit_writers() is False


def test_has_explicit_writers_true_after_configure_writers():
    obs = Observer()
    obs.configure_writers([MemoryWriter()])
    assert obs.has_explicit_writers() is True


def test_has_explicit_writers_true_after_configure_writers_empty():
    """configure_writers([]) is an explicit 'no writers' — must be
    distinguishable from 'never called'. This is the whole point of the sentinel."""
    obs = Observer()
    obs.configure_writers([])
    assert obs.has_explicit_writers() is True


def test_is_running_reflects_start_shutdown_state():
    obs = Observer()
    assert obs.is_running() is False


# ------------------------------------------------------------------------
# Writer-start resilience (#1049)
# ------------------------------------------------------------------------


class _RaisingStartWriter:
    """Writer whose start() raises. Post-start / write / shutdown never fire."""

    def __init__(self, exc: BaseException):
        self._exc = exc

    async def start(self) -> None:
        raise self._exc

    async def write(self, event: Event) -> None:  # pragma: no cover — never called
        raise AssertionError("write() should not be reached")

    async def shutdown(self) -> None:  # pragma: no cover — never called
        raise AssertionError("shutdown() should not be reached")


async def test_start_skips_writer_that_fails_with_oserror(caplog):
    """A pending writer whose start() raises OSError does not tank observer
    bring-up. The good writer still registers; a single WARN is emitted."""
    import logging

    from railtracks.observability import configure

    configure.reset_for_tests()  # reset the once-per-process warning flag
    good = MemoryWriter()
    bad = _RaisingStartWriter(OSError(30, "Read-only file system"))

    obs = Observer()
    obs.configure_writers([bad, good])
    try:
        with caplog.at_level(logging.WARNING, logger="railtracks"):
            await obs.start()
        assert obs.is_running() is True
        assert "writer-0" not in obs._writers
        assert "writer-1" in obs._writers
        assert good.started is True
        readonly_warnings = [
            r for r in caplog.records if "could not write to disk" in r.getMessage()
        ]
        assert len(readonly_warnings) == 1
        assert "RAILTRACKS_DISABLE_EVENTS=True" in readonly_warnings[0].getMessage()
    finally:
        await obs.shutdown()


async def test_start_flips_running_when_all_writers_fail(caplog):
    """Even with every writer failing, the observer must reach _running=True so
    later publish() calls fail loudly instead of silently blocking."""
    import logging

    from railtracks.observability import configure

    configure.reset_for_tests()
    obs = Observer()
    obs.configure_writers([_RaisingStartWriter(OSError("nope"))])
    try:
        with caplog.at_level(logging.WARNING, logger="railtracks"):
            await obs.start()
        assert obs.is_running() is True
        assert obs._writers == {}
        # publish() should raise RuntimeError, not hang or drop silently.
        # (Observer._writers is empty, so it fans out to zero queues.)
        await obs.publish(_event("e1"))
    finally:
        await obs.shutdown()


async def test_readonly_disk_warning_emitted_only_once(caplog):
    """Two failing writers in one start() batch → still just one WARN. The
    helper's once-per-process guard prevents log spam."""
    import logging

    from railtracks.observability import configure

    configure.reset_for_tests()
    obs = Observer()
    obs.configure_writers(
        [
            _RaisingStartWriter(OSError("first")),
            _RaisingStartWriter(OSError("second")),
        ]
    )
    try:
        with caplog.at_level(logging.WARNING, logger="railtracks"):
            await obs.start()
        readonly_warnings = [
            r for r in caplog.records if "could not write to disk" in r.getMessage()
        ]
        assert len(readonly_warnings) == 1
    finally:
        await obs.shutdown()


async def test_start_logs_wider_warning_for_non_oserror_startup_failure(caplog):
    """A non-OSError writer.start() failure gets a plain WARN (not the shared
    'read-only disk' message)."""
    import logging

    from railtracks.observability import configure

    configure.reset_for_tests()
    obs = Observer()
    obs.configure_writers([_RaisingStartWriter(RuntimeError("bad wiring"))])
    try:
        with caplog.at_level(logging.WARNING, logger="railtracks"):
            await obs.start()
        assert obs.is_running() is True
        assert obs._writers == {}
        msgs = [r.getMessage() for r in caplog.records]
        assert any("failed to start" in m and "RuntimeError" in m for m in msgs)
        assert not any("could not write to disk" in m for m in msgs)
    finally:
        await obs.shutdown()
