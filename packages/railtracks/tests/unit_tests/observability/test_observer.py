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
    obs = Observer()
    with pytest.raises(RuntimeError):
        await obs.register(MemoryWriter(), "w")


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
