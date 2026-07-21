from __future__ import annotations

import asyncio

from railtracks.observability import (
    SCOPE_SESSION,
    Event,
    configure,
    configure_writers,
    publish,
    publish_event,
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


async def _drain_and_shutdown() -> None:
    if publish._pending_tasks:
        await asyncio.gather(
            *list(publish._pending_tasks), return_exceptions=True
        )
    if configure._observer._running:
        await configure._observer.shutdown()


async def test_concurrentensure_started_coalesces():
    """Two ensure_started calls at once must not both try to register the
    same writer — Observer's start() coalesces via its internal lock."""
    writer = _CollectingWriter()
    configure_writers([writer])

    # Kick off five ensure_started calls concurrently.
    results = await asyncio.gather(*[configure.ensure_started() for _ in range(5)])

    # All returned the same singleton, only one actually did the registration.
    assert all(r is configure._observer for r in results)
    assert configure._observer._running is True

    # Registration succeeded — publishing works end-to-end.
    event = _make_session_event()
    publish_event(event)
    await _drain_and_shutdown()
    assert writer.events == [event]


async def testreset_for_tests_allows_fresh_start():
    # First run.
    writer1 = _CollectingWriter()
    configure_writers([writer1])
    event1 = _make_session_event("first")
    publish_event(event1)
    await _drain_and_shutdown()
    assert writer1.events == [event1]

    first_observer = configure._observer

    # Reset — should swap in a fresh Observer.
    configure.reset_for_tests()
    publish.reset_for_tests()
    assert configure._observer is not first_observer
    assert configure._observer._running is False
    assert configure._observer._pending_writers == []
    assert publish._pending_tasks == set()

    # Fresh start with a different writer.
    writer2 = _CollectingWriter()
    configure_writers([writer2])
    event2 = _make_session_event("second")
    publish_event(event2)
    await _drain_and_shutdown()
    assert writer2.events == [event2]
    # writer1 was not touched by the second run.
    assert writer1.events == [event1]
