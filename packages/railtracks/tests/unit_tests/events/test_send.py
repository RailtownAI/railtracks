"""End-to-end emit path: pipe(event) -> resolve parent -> publish -> writer."""

import datetime

import railtracks.context.central as central
from railtracks.events._base import NodeParent, NoParent
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


async def test_pipe_resolves_parent_and_publishes_raw_payload():
    _register("sess-1")
    manager = central.ContextVarScopeManager()

    with manager.enter_node("caller"):
        with manager.enter_node_body():
            with manager.enter_node("n1"):
                events = await _emit(
                    NodeInvocation(
                        name="Agent",
                        node_id="n1",
                        node_type="agent",
                        args=(1,),
                        kwargs={"x": 2},
                    )
                )

    assert len(events) == 1
    ev = events[0]
    assert ev.event_type == "node.invocation"
    assert ev.scope_type == "session"
    assert ev.scope_id == "sess-1"

    p = ev.payload
    assert p["node_id"] == "n1"
    assert p["name"] == "Agent"
    assert p["node_type"] == "agent"
    # parent is the resolved Parent object (serialization is deferred to the writers)
    assert p["parent"] == NodeParent(node_id="caller", middleware_id=None)
    # payload values are passed through untouched: tuple stays tuple, datetime stays datetime
    assert p["args"] == (1,)
    assert p["kwargs"] == {"x": 2}
    assert isinstance(p["timestamp"], datetime.datetime)


async def test_pipe_root_node_has_noparent():
    _register("sess-2")
    manager = central.ContextVarScopeManager()

    with manager.enter_node("root"):
        events = await _emit(
            NodeInvocation(
                name="Root", node_id="root", node_type="agent", args=(), kwargs={}
            )
        )

    assert events[0].payload["parent"] == NoParent()
