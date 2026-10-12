import asyncio
import logging
import threading
import time
from collections.abc import Callable, Coroutine, Iterator
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
        self.start_calls = 0
        self.shutdown_called = False
        self.write_threads: set[int] = set()
        self._sleep = sleep_before_write
        self._raise = raise_on_write

    async def start(self) -> None:
        self.started = True
        self.start_calls += 1

    async def write(self, event: Event) -> None:
        self.write_threads.add(threading.get_ident())
        if self._sleep:
            await asyncio.sleep(self._sleep)
        if self._raise:
            raise RuntimeError("boom")
        self.events.append(event)

    async def shutdown(self) -> None:
        self.shutdown_called = True


class GatedWriter(MemoryWriter):
    """Blocks every write until `gate` is set. Tests must set it before finishing."""

    def __init__(self) -> None:
        super().__init__()
        self.gate = threading.Event()

    async def write(self, event: Event) -> None:
        await asyncio.to_thread(self.gate.wait)
        self.events.append(event)


def _event(scope_id: str = "s1") -> Event:
    return Event(
        event_type="test",
        stamp=Timestamp.now(),
        scope_type=SCOPE_SESSION,
        scope_id=scope_id,
    )


async def _settle(obs: Observer) -> None:
    """Wait until every callback already handed to the observer loop has run."""
    assert obs._loop is not None
    await asyncio.wrap_future(
        asyncio.run_coroutine_threadsafe(asyncio.sleep(0), obs._loop)
    )


async def _wait_until(condition: Callable[[], bool], timeout: float = 5.0) -> None:
    deadline = time.monotonic() + timeout
    while not condition():
        if time.monotonic() > deadline:
            raise AssertionError("condition not met in time")
        await asyncio.sleep(0.005)


@pytest.fixture
def make_observer() -> Iterator[Callable[[], Observer]]:
    """Build Observers whose background threads are stopped after the test."""
    created: list[Observer] = []

    def factory() -> Observer:
        obs = Observer()
        created.append(obs)
        return obs

    yield factory
    for obs in created:
        obs._stop_thread()


# ------------------------------------------------------------------------
# Fan-out and writer behaviour
# ------------------------------------------------------------------------


async def test_fan_out_to_multiple_writers(make_observer):
    a, b = MemoryWriter(), MemoryWriter()
    async with make_observer() as obs:
        await obs.register(a, "a")
        await obs.register(b, "b")
        await obs.publish(_event("e1"))
        await obs.publish(_event("e2"))
    assert [e.scope_id for e in a.events] == ["e1", "e2"]
    assert [e.scope_id for e in b.events] == ["e1", "e2"]


async def test_writer_start_and_shutdown_are_called(make_observer):
    w = MemoryWriter()
    async with make_observer() as obs:
        await obs.register(w, "w")
        assert w.started is True
    assert w.shutdown_called is True


async def test_slow_writer_does_not_block_fast_writer(make_observer):
    slow = GatedWriter()
    fast = MemoryWriter()
    obs = make_observer()
    await obs.start()
    try:
        await obs.register(slow, "slow")
        await obs.register(fast, "fast")
        for i in range(5):
            await obs.publish(_event(f"e{i}"))
        await _wait_until(lambda: len(fast.events) == 5)
        assert slow.events == []
    finally:
        slow.gate.set()
        await obs.shutdown()
    assert len(slow.events) == 5


async def test_writer_exception_does_not_kill_observer(make_observer):
    bad = MemoryWriter(raise_on_write=True)
    good = MemoryWriter()
    async with make_observer() as obs:
        await obs.register(bad, "bad")
        await obs.register(good, "good")
        await obs.publish(_event("e1"))
        await obs.publish(_event("e2"))
    assert [e.scope_id for e in good.events] == ["e1", "e2"]
    assert bad.events == []
    assert bad.shutdown_called is True


async def test_shutdown_drains_pending_events(make_observer):
    slow = MemoryWriter(sleep_before_write=0.005)
    obs = make_observer()
    await obs.start()
    await obs.register(slow, "slow")
    for i in range(5):
        await obs.publish(_event(f"e{i}"))
    await obs.shutdown()
    assert len(slow.events) == 5


async def test_publish_after_shutdown_raises(make_observer):
    obs = make_observer()
    await obs.start()
    await obs.register(MemoryWriter(), "w")
    await obs.shutdown()
    with pytest.raises(RuntimeError):
        await obs.publish(_event())


async def test_is_observing_needs_a_running_observer_with_a_writer(make_observer):
    obs = make_observer()
    assert obs.is_observing is False

    await obs.start()
    assert obs.is_observing is False

    await obs.register(MemoryWriter(), "w")
    assert obs.is_observing is True

    await obs.shutdown()
    assert obs.is_observing is False


async def test_register_when_not_running_raises(make_observer):
    """Public register still requires start() first. Pre-start batch
    registration goes through configure_writers()."""
    obs = make_observer()
    with pytest.raises(RuntimeError, match="Observer is not running"):
        await obs.register(MemoryWriter(), "w")


async def test_configure_writers_then_start_registers_pending(make_observer):
    """The Observer-level batch flow: configure_writers([...]) then start()
    registers each with auto-name writer-{i}."""
    a, b = MemoryWriter(), MemoryWriter()
    obs = make_observer()
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


async def test_configure_writers_after_start_raises(make_observer):
    obs = make_observer()
    await obs.start()
    try:
        with pytest.raises(
            RuntimeError, match="configure_writers must be called before"
        ):
            obs.configure_writers([MemoryWriter()])
    finally:
        await obs.shutdown()


async def test_concurrent_start_coalesces(make_observer):
    """Concurrent Observer.start() calls register the pending writers once. No
    duplicate-name errors."""
    a, b = MemoryWriter(), MemoryWriter()
    obs = make_observer()
    obs.configure_writers([a, b])
    await asyncio.gather(*[obs.start() for _ in range(5)])
    try:
        assert obs._running is True
        assert set(obs._writers.keys()) == {"writer-0", "writer-1"}
        assert a.start_calls == 1
        assert b.start_calls == 1
    finally:
        await asyncio.gather(*[obs.shutdown() for _ in range(5)])
    assert obs._running is False
    assert a.shutdown_called is True


async def test_register_duplicate_name_raises(make_observer):
    async with make_observer() as obs:
        await obs.register(MemoryWriter(), "same")
        with pytest.raises(ValueError):
            await obs.register(MemoryWriter(), "same")


async def test_unregister_cleans_up_writer_and_stops_delivery(make_observer):
    a, b = MemoryWriter(), MemoryWriter()
    async with make_observer() as obs:
        await obs.register(a, "a")
        await obs.register(b, "b")
        await obs.publish(_event("e1"))
        await obs.unregister("a")
        assert a.shutdown_called is True
        await obs.publish(_event("e2"))
    assert [e.scope_id for e in a.events] == ["e1"]
    assert [e.scope_id for e in b.events] == ["e1", "e2"]


async def test_unregister_unknown_name_raises(make_observer):
    async with make_observer() as obs:
        with pytest.raises(KeyError):
            await obs.unregister("nope")


async def test_drop_oldest_when_queue_full(make_observer):
    gated = GatedWriter()
    obs = make_observer()
    await obs.start()
    try:
        await obs.register(gated, "gated", maxsize=3, policy=QueuePolicy.DROP_OLDEST)
        await obs.publish(_event("e0"))
        await _settle(obs)  # the consumer now holds e0, blocked on the gate
        for i in range(1, 6):
            await obs.publish(_event(f"e{i}"))
        await _settle(obs)
        assert obs._drops["gated"] == 2
    finally:
        gated.gate.set()
        await obs.shutdown()
    assert [e.scope_id for e in gated.events] == ["e0", "e3", "e4", "e5"]


# ------------------------------------------------------------------------
# Writer-start resilience (#1049)
# ------------------------------------------------------------------------


class _RaisingStartWriter:
    async def start(self) -> None:
        raise OSError(30, "Read-only file system")

    async def write(self, event: Event) -> None:  # pragma: no cover
        raise AssertionError("write() should not be reached")

    async def shutdown(self) -> None:  # pragma: no cover
        raise AssertionError("shutdown() should not be reached")


async def test_start_skips_writer_whose_start_fails(caplog, make_observer):
    """A pending writer whose start() raises does not tank observer bring-up.
    The good writer still registers and a WARN is logged."""
    good = MemoryWriter()
    obs = make_observer()
    obs.configure_writers([_RaisingStartWriter(), good])
    try:
        with caplog.at_level(logging.WARNING, logger="railtracks"):
            await obs.start()
        assert obs._running is True
        assert "writer-0" not in obs._writers
        assert "writer-1" in obs._writers
        assert good.started is True
        assert any("failed to start" in r.getMessage() for r in caplog.records)
    finally:
        await obs.shutdown()


# ------------------------------------------------------------------------
# Reference-counted lifecycle (#1605)
# ------------------------------------------------------------------------


async def test_writers_stay_up_until_the_last_shutdown(make_observer):
    w = MemoryWriter()
    obs = make_observer()
    obs.configure_writers([w])
    await obs.start()
    await obs.start()

    await obs.shutdown()
    assert obs._running is True
    assert w.shutdown_called is False
    await obs.publish(_event("after-first-shutdown"))

    await obs.shutdown()
    assert obs._running is False
    assert w.shutdown_called is True
    assert [e.scope_id for e in w.events] == ["after-first-shutdown"]


async def test_earlier_shutdown_waits_for_its_events_to_be_written(make_observer):
    w = MemoryWriter(sleep_before_write=0.01)
    obs = make_observer()
    obs.configure_writers([w])
    await obs.start()
    await obs.start()
    try:
        for i in range(5):
            await obs.publish(_event(f"e{i}"))
        await obs.shutdown()
        assert [e.scope_id for e in w.events] == [f"e{i}" for i in range(5)]
        assert w.shutdown_called is False
    finally:
        await obs.shutdown()


async def test_earlier_shutdown_does_not_hang_when_its_flush_marker_is_dropped(
    make_observer,
):
    gated = GatedWriter()
    obs = make_observer()
    await obs.start()
    await obs.start()
    try:
        await obs.register(gated, "gated", maxsize=2)
        await obs.publish(_event("e0"))
        await _settle(obs)  # the consumer now holds e0, blocked on the gate
        await obs.publish(_event("e1"))
        await _settle(obs)

        first_shutdown = asyncio.ensure_future(obs.shutdown())
        await asyncio.sleep(0)  # let the shutdown hand its release to the observer loop
        await _settle(obs)  # queue is [e1, marker]
        for i in range(2, 4):  # e2 evicts e1, e3 evicts the marker
            await obs.publish(_event(f"e{i}"))

        await asyncio.wait_for(first_shutdown, timeout=5)
        assert gated.events == []
    finally:
        gated.gate.set()
        await obs.shutdown()


async def test_extra_shutdowns_are_ignored(make_observer):
    w = MemoryWriter()
    obs = make_observer()
    obs.configure_writers([w])
    await obs.start()
    await obs.shutdown()
    await obs.shutdown()
    await obs.shutdown()
    assert obs._users == 0

    await obs.start()
    try:
        assert obs._running is True
        assert w.start_calls == 2
    finally:
        await obs.shutdown()
    assert obs._running is False


async def test_shutdown_before_any_start_does_not_spawn_a_thread(make_observer):
    obs = make_observer()
    await obs.shutdown()
    assert obs._thread is None


async def test_observer_restarts_after_a_full_shutdown(make_observer):
    w = MemoryWriter()
    obs = make_observer()
    obs.configure_writers([w])
    for i in range(3):
        await obs.start()
        await obs.publish(_event(f"run{i}"))
        await obs.shutdown()
    assert [e.scope_id for e in w.events] == ["run0", "run1", "run2"]
    assert w.start_calls == 3


async def test_cancelled_shutdown_still_drains(make_observer):
    w = MemoryWriter(sleep_before_write=0.01)
    obs = make_observer()
    obs.configure_writers([w])
    await obs.start()
    for i in range(5):
        await obs.publish(_event(f"e{i}"))

    pending = asyncio.ensure_future(obs.shutdown())
    await asyncio.sleep(0.005)
    pending.cancel()
    with pytest.raises(asyncio.CancelledError):
        await pending

    await _wait_until(lambda: w.shutdown_called)
    assert len(w.events) == 5


# ------------------------------------------------------------------------
# Background loop and cross-thread use (#1605)
# ------------------------------------------------------------------------


async def test_writers_run_on_the_observer_thread(make_observer):
    w = MemoryWriter()
    obs = make_observer()
    obs.configure_writers([w])
    async with obs:
        await obs.publish(_event())
        assert obs.loop is not None
        assert obs.loop is not asyncio.get_running_loop()
        observer_thread = obs._thread
    assert observer_thread is not None
    assert w.write_threads == {observer_thread.ident}


async def test_loop_property_is_none_while_stopped(make_observer):
    obs = make_observer()
    assert obs.loop is None
    await obs.start()
    assert obs.loop is obs._loop
    await obs.shutdown()
    assert obs.loop is None


async def test_one_thread_serves_every_start(make_observer):
    obs = make_observer()
    await obs.start()
    first_thread = obs._thread
    await obs.shutdown()
    await obs.start()
    try:
        assert obs._thread is first_thread
    finally:
        await obs.shutdown()


def test_runs_on_separate_threads_share_the_observer(make_observer):
    """Each thread drives its own asyncio.run, as `Flow.invoke` does, and each one
    takes and releases a reference. The first to finish must not stop the other."""
    w = MemoryWriter()
    obs = make_observer()
    obs.configure_writers([w])
    first_started = threading.Event()
    second_done = threading.Event()
    errors: list[BaseException] = []

    async def first_run() -> None:
        await obs.start()
        first_started.set()
        await asyncio.to_thread(second_done.wait, 5)
        await obs.publish(_event("first"))
        await obs.shutdown()

    async def second_run() -> None:
        await asyncio.to_thread(first_started.wait, 5)
        await obs.start()
        await obs.publish(_event("second"))
        await obs.shutdown()
        second_done.set()

    def run(coro_fn: Callable[[], Coroutine[object, object, None]]) -> None:
        try:
            asyncio.run(coro_fn())
        except BaseException as exc:  # noqa: BLE001 - surfaced by the assertion below
            errors.append(exc)

    threads = [
        threading.Thread(target=run, args=(first_run,)),
        threading.Thread(target=run, args=(second_run,)),
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=10)

    assert errors == []
    assert sorted(e.scope_id for e in w.events) == ["first", "second"]
    assert w.shutdown_called is True
    assert obs._running is False


async def test_publish_from_many_threads_delivers_every_event(make_observer):
    w = MemoryWriter()
    obs = make_observer()
    obs.configure_writers([w])
    threads, per_thread = 8, 250

    def publish_many(prefix: int) -> None:
        for i in range(per_thread):
            obs.publish_nowait(_event(f"{prefix}-{i}"))

    async with obs:
        await asyncio.gather(
            *[asyncio.to_thread(publish_many, t) for t in range(threads)]
        )

    assert len(w.events) == threads * per_thread
    for t in range(threads):
        from_thread = [e.scope_id for e in w.events if e.scope_id.startswith(f"{t}-")]
        assert from_thread == [f"{t}-{i}" for i in range(per_thread)]


async def test_register_from_the_observer_loop_does_not_deadlock(make_observer):
    obs = make_observer()
    await obs.start()
    try:
        assert obs._loop is not None
        on_loop = asyncio.run_coroutine_threadsafe(
            obs.register(MemoryWriter(), "late"), obs._loop
        )
        await asyncio.wait_for(asyncio.wrap_future(on_loop), timeout=5)
        assert "late" in obs._writers
    finally:
        await obs.shutdown()


async def test_dead_observer_thread_is_replaced_with_fresh_state(make_observer):
    """A forked child inherits the observer's state but not its thread."""
    w = MemoryWriter()
    obs = make_observer()
    obs.configure_writers([w])
    await obs.start()
    old_loop = obs._loop
    assert old_loop is not None

    dead = threading.Thread(target=lambda: None)
    dead.start()
    dead.join()
    live_thread = obs._thread
    orphaned = [entry.task for entry in obs._writers.values()]
    obs._thread = dead  # as seen from a forked child

    await obs.start()
    try:
        assert obs._loop is not old_loop
        assert obs._users == 1
        assert w.start_calls == 2
        await obs.publish(_event("in-child"))
    finally:
        await obs.shutdown()
        for task in orphaned:
            old_loop.call_soon_threadsafe(task.cancel)
        asyncio.run_coroutine_threadsafe(asyncio.sleep(0), old_loop).result(timeout=5)
        old_loop.call_soon_threadsafe(old_loop.stop)
        assert live_thread is not None
        live_thread.join(timeout=5)
        old_loop.close()
    assert [e.scope_id for e in w.events] == ["in-child"]


async def test_stop_thread_cancels_writers_and_stops_the_loop(make_observer):
    gated = GatedWriter()
    obs = make_observer()
    obs.configure_writers([gated])
    await obs.start()
    await obs.publish(_event())
    thread = obs._thread
    assert thread is not None

    try:
        obs._stop_thread()
    finally:
        gated.gate.set()
    assert not thread.is_alive()
    assert obs._running is False
    assert obs._loop is None
