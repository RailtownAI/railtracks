"""End-to-end emit path: pipe(event) -> resolve relationships -> publish -> writer."""

import datetime

import railtracks.context.central as central
from railtracks.events.node import NodeInvocation
from railtracks.events.send import pipe
from railtracks.observability import (
    Event,
    configure_writers,
    ensure_started,
    shutdown,
)
from railtracks.utils.config import ExecutorConfig


class _Collecting:
    def __init__(self):
        self.events: list[Event] = []

    async def start(self):
        pass

    async def write(self, event: Event):
        self.events.append(event)

    async def shutdown(self):
        pass


def _register(session_id="sess-1"):
    central.register_globals(
        session_id=session_id,
        rt_publisher=None,
        executor_config=ExecutorConfig(),
        global_context_vars={},
    )


async def _emit(event):
    writer = _Collecting()
    configure_writers([writer])
    await ensure_started()
    await pipe(event)
    await shutdown()  # drains per-writer queues so delivery is deterministic
    return writer.events


async def test_pipe_resolves_relationships_and_publishes_payload():
    _register("sess-1")
    manager = central.ContextVarScopeManager()

    with manager.enter_node("caller"):
        with manager.enter_node_body():
            with manager.enter_node("n1"):
                events = await _emit(NodeInvocation(args=(1,), kwargs={"x": 2}))

    assert len(events) == 1
    ev = events[0]
    assert ev.event_type == "node.invocation"
    assert ev.scope_type == "session"
    assert ev.scope_id == "sess-1"

    p = ev.payload
    # the resolved relationships: self is n1, nested inside the caller
    assert p["parent"] == {"parent_type": "node", "node_id": "n1"}
    assert p["spatial_parent"] == {"spatial_type": "node", "node_id": "caller"}
    # payload values are passed through untouched: tuple stays tuple, datetime stays datetime
    assert p["args"] == (1,)
    assert p["kwargs"] == {"x": 2}
    assert isinstance(p["timestamp"], datetime.datetime)


async def test_pipe_root_node_has_no_enclosing_node():
    _register("sess-2")
    manager = central.ContextVarScopeManager()

    with manager.enter_node("root"):
        events = await _emit(NodeInvocation(args=(), kwargs={}))

    p = events[0].payload
    assert p["parent"] == {"parent_type": "node", "node_id": "root"}
    assert p["spatial_parent"] == {"spatial_type": "node", "node_id": None}
