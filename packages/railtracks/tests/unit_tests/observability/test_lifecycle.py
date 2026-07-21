from __future__ import annotations

import asyncio

from railtracks.observability import (
    SCOPE_SESSION,
    Event,
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
    assert all(r is configure._observer for r in results)
    assert configure._observer._running is True

    # Registration succeeded — publishing works end-to-end.
    event = _make_session_event()
    publish_event(event)
    await shutdown()
    assert writer.events == [event]


async def test_reset_for_tests_swaps_in_fresh_observer():
    # First run.
    writer1 = _CollectingWriter()
    configure_writers([writer1])
    await ensure_started()
    event1 = _make_session_event("first")
    publish_event(event1)
    await shutdown()
    assert writer1.events == [event1]

    first_observer = configure._observer

    # Reset — should swap in a fresh Observer.
    configure.reset_for_tests()
    assert configure._observer is not first_observer
    assert configure._observer._running is False
    assert configure._observer._pending_writers == []

    # Fresh start with a different writer.
    writer2 = _CollectingWriter()
    configure_writers([writer2])
    await ensure_started()
    event2 = _make_session_event("second")
    publish_event(event2)
    await shutdown()
    assert writer2.events == [event2]
    # writer1 was not touched by the second run.
    assert writer1.events == [event1]
