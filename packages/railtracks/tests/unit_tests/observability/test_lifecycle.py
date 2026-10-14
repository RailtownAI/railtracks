from __future__ import annotations

import asyncio
import threading

from railtracks.observability import (
    SCOPE_SESSION,
    Event,
    JsonlWriter,
    configure,
    configure_writers,
    ensure_started,
    publish_event,
    shutdown,
)


class _CollectingWriter:
    def __init__(self) -> None:
        self.events: list[Event] = []

    async def start(self) -> None:
        pass

    async def write(self, event: Event) -> None:
        self.events.append(event)

    async def shutdown(self) -> None:
        pass


def _make_session_event(event_type: str = "test.event") -> Event:
    return Event(
        event_type=event_type,
        scope_type=SCOPE_SESSION,
        scope_id="s1",
        payload={},
    )


async def test_concurrent_ensure_started_coalesces():
    """Concurrent ensure_started() calls must not both register the same
    pending writers — Observer's start() coalesces via its internal lock."""
    writer = _CollectingWriter()
    configure_writers([writer])

    # Kick off five ensure_started() calls concurrently.
    results = await asyncio.gather(*[ensure_started() for _ in range(5)])

    # All returned the same singleton, only one actually did the registration.
    assert all(r is configure.observer for r in results)
    assert configure.observer._running is True

    # Registration succeeded — publishing works end-to-end.
    event = _make_session_event()
    await publish_event(event)
    for _ in results:
        await shutdown()
    assert writer.events == [event]
    assert configure.observer._running is False


async def test_reset_for_tests_swaps_in_fresh_observer():
    # First run.
    writer1 = _CollectingWriter()
    configure_writers([writer1])
    await ensure_started()
    event1 = _make_session_event("first")
    await publish_event(event1)
    await shutdown()
    assert writer1.events == [event1]

    first_observer = configure.observer

    # Reset — should swap in a fresh Observer.
    configure.reset_for_tests()
    assert configure.observer is not first_observer
    assert configure.observer._running is False
    assert configure.observer._pending_writers == []

    # Fresh start with a different writer.
    writer2 = _CollectingWriter()
    configure_writers([writer2])
    await ensure_started()
    event2 = _make_session_event("second")
    await publish_event(event2)
    await shutdown()
    assert writer2.events == [event2]
    # writer1 was not touched by the second run.
    assert writer1.events == [event1]


def test_first_runs_on_separate_threads_inject_one_default_writer(
    monkeypatch, tmp_path
):
    """Runs starting together on different threads must not both inject the default
    JsonlWriter, nor try to configure writers on an Observer the other just started."""
    monkeypatch.delenv("RAILTRACKS_DISABLE_EVENTS", raising=False)
    monkeypatch.setenv("RAILTRACKS_EVENTS_DIR", str(tmp_path / "events"))
    threads = 8
    barrier = threading.Barrier(threads)
    errors: list[BaseException] = []
    writer_counts: list[int] = []

    async def run() -> None:
        observer = await ensure_started()
        writer_counts.append(len(observer._writers))
        await shutdown()

    def worker() -> None:
        barrier.wait(timeout=5)
        try:
            asyncio.run(run())
        except BaseException as exc:  # noqa: BLE001 - surfaced by the assertion below
            errors.append(exc)

    workers = [threading.Thread(target=worker) for _ in range(threads)]
    for t in workers:
        t.start()
    for t in workers:
        t.join(timeout=10)

    assert errors == []
    assert writer_counts == [1] * threads
    pending = configure.observer._pending_writers
    assert len(pending) == 1
    assert isinstance(pending[0], JsonlWriter)
    assert configure.observer._running is False
