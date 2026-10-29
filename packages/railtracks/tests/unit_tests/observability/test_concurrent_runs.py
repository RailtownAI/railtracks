"""Overlapping top-level runs each record every one of their events (#1605)."""

from __future__ import annotations

import asyncio
import threading
from concurrent.futures import ThreadPoolExecutor

import railtracks as rt
from railtracks.observability import Event, configure_writers


class _CollectingWriter:
    def __init__(self) -> None:
        self.events: list[Event] = []

    def start(self) -> None:
        pass

    def write(self, event: Event) -> None:
        self.events.append(event)

    def shutdown(self) -> None:
        pass


def _completed_flows(writer: _CollectingWriter) -> list[str]:
    names = {
        e.scope_id: e.payload["flow_name"]
        for e in writer.events
        if e.event_type == "session.started"
    }
    return sorted(
        names[e.scope_id] for e in writer.events if e.event_type == "session.completed"
    )


@rt.function_node
async def quick() -> str:
    """Finish straight away."""
    return "quick"


@rt.function_node
async def slow() -> str:
    """Finish after the quick flow has already completed."""
    await asyncio.sleep(0.2)
    return "slow"


async def test_flows_gathered_on_one_loop_all_record_completion():
    writer = _CollectingWriter()
    configure_writers([writer])

    results = await asyncio.gather(
        rt.Flow("quick-flow", quick).ainvoke(),
        rt.Flow("slow-flow", slow).ainvoke(),
    )

    assert results == ["quick", "slow"]
    assert _completed_flows(writer) == ["quick-flow", "slow-flow"]


def test_flows_on_separate_threads_both_succeed_and_record_completion():
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

    assert _completed_flows(writer) == ["flow-A", "flow-B"]
