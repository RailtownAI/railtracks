"""Overlapping top-level runs share one Observer without losing events (#1605)."""

from __future__ import annotations

import asyncio
import threading
from concurrent.futures import ThreadPoolExecutor

import railtracks as rt
from railtracks.observability import Event, configure, configure_writers


class _CollectingWriter:
    def __init__(self) -> None:
        self.events: list[Event] = []

    async def start(self) -> None:
        pass

    async def write(self, event: Event) -> None:
        self.events.append(event)

    async def shutdown(self) -> None:
        pass


def _completed_flows(writer: _CollectingWriter) -> list[str]:
    """Names of the flows whose `session.completed` event reached the writer."""
    names = {
        e.scope_id: e.payload["flow_name"]
        for e in list(writer.events)
        if e.event_type == "session.started"
    }
    return [
        names[e.scope_id]
        for e in list(writer.events)
        if e.event_type == "session.completed"
    ]


@rt.function_node
async def quick() -> str:
    """Finish straight away."""
    return "quick"


@rt.function_node
async def slow() -> str:
    """Finish after `quick` has already returned."""
    await asyncio.sleep(0.2)
    return "slow"


async def test_flows_gathered_on_one_loop_record_every_completion():
    writer = _CollectingWriter()
    configure_writers([writer])

    results = await asyncio.gather(
        rt.Flow("quick-flow", quick).ainvoke(),
        rt.Flow("slow-flow", slow).ainvoke(),
    )

    assert results == ["quick", "slow"]
    assert sorted(_completed_flows(writer)) == ["quick-flow", "slow-flow"]
    assert configure.observer._running is False


def test_flows_on_threads_when_the_later_starter_finishes_first():
    writer = _CollectingWriter()
    configure_writers([writer])
    a_running = threading.Event()
    b_done = threading.Event()

    @rt.function_node
    def long_task() -> str:
        """Hold flow A open until flow B has finished."""
        a_running.set()
        b_done.wait(timeout=5)
        return "A"

    @rt.function_node
    def short_task() -> str:
        """Finish straight away."""
        return "B"

    def run_b() -> str:
        a_running.wait(timeout=5)
        try:
            return rt.Flow("flow-B", short_task).invoke()
        finally:
            b_done.set()

    with ThreadPoolExecutor(max_workers=2) as pool:
        future_a = pool.submit(rt.Flow("flow-A", long_task).invoke)
        future_b = pool.submit(run_b)
        assert future_b.result(timeout=10) == "B"
        assert future_a.result(timeout=10) == "A"

    assert _completed_flows(writer) == ["flow-B", "flow-A"]
    assert configure.observer._running is False


def test_flows_on_threads_when_the_first_starter_finishes_first():
    """The thread that started the Observer exits its event loop while the other run
    is still emitting, so writers must not live on that loop."""
    writer = _CollectingWriter()
    configure_writers([writer])
    a_running = threading.Event()
    b_running = threading.Event()
    a_done = threading.Event()

    @rt.function_node
    def first_task() -> str:
        """Return once flow B is running."""
        a_running.set()
        b_running.wait(timeout=5)
        return "A"

    @rt.function_node
    def second_task() -> str:
        """Return only after flow A's thread has finished its run."""
        b_running.set()
        a_done.wait(timeout=5)
        return "B"

    def run_a() -> str:
        try:
            return rt.Flow("flow-A", first_task).invoke()
        finally:
            a_done.set()

    def run_b() -> str:
        a_running.wait(timeout=5)
        return rt.Flow("flow-B", second_task).invoke()

    with ThreadPoolExecutor(max_workers=2) as pool:
        future_a = pool.submit(run_a)
        future_b = pool.submit(run_b)
        assert future_a.result(timeout=10) == "A"
        assert future_b.result(timeout=10) == "B"

    assert _completed_flows(writer) == ["flow-A", "flow-B"]
    assert configure.observer._running is False


def test_returned_run_has_its_events_written_while_another_run_is_active():
    writer = _CollectingWriter()
    configure_writers([writer])
    a_running = threading.Event()
    release_a = threading.Event()

    @rt.function_node
    def held_task() -> str:
        """Stay open until the test releases it."""
        a_running.set()
        release_a.wait(timeout=5)
        return "A"

    with ThreadPoolExecutor(max_workers=1) as pool:
        future_a = pool.submit(rt.Flow("flow-A", held_task).invoke)
        try:
            assert a_running.wait(timeout=5)
            assert rt.Flow("flow-B", quick).invoke() == "quick"
            assert _completed_flows(writer) == ["flow-B"]
            assert configure.observer._running is True
        finally:
            release_a.set()
        assert future_a.result(timeout=10) == "A"

    assert _completed_flows(writer) == ["flow-B", "flow-A"]


def test_burst_of_flows_on_a_thread_pool_records_every_session():
    writer = _CollectingWriter()
    configure_writers([writer])
    flows = 16

    @rt.function_node
    async def echo(n: int) -> int:
        """Return the number after yielding once."""
        await asyncio.sleep(0.01)
        return n

    def run(n: int) -> int:
        return rt.Flow(f"flow-{n}", echo).invoke(n)

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(run, range(flows)))

    assert results == list(range(flows))
    assert sorted(_completed_flows(writer)) == sorted(f"flow-{n}" for n in range(flows))
    for scope_id in {e.scope_id for e in writer.events}:
        session_events = [e.event_type for e in writer.events if e.scope_id == scope_id]
        assert session_events[0] == "session.started"
        assert session_events[-1] == "session.completed"
    assert configure.observer._running is False


async def test_mixed_async_and_threaded_flows_share_the_observer():
    writer = _CollectingWriter()
    configure_writers([writer])

    async_result, thread_result = await asyncio.gather(
        rt.Flow("async-flow", slow).ainvoke(),
        asyncio.to_thread(rt.Flow("thread-flow", quick).invoke),
    )

    assert (async_result, thread_result) == ("slow", "quick")
    assert sorted(_completed_flows(writer)) == ["async-flow", "thread-flow"]
    assert configure.observer._running is False
