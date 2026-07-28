"""Hot-path integration: run a real node graph and assert the emitted node events.

Unlike `test_send.py` (which drives `pipe` directly against a synthetic scope), this runs
`rt.call` end-to-end and checks that the emission sites in `nodes.py`,
`execution_strategy.py`, and `state.py` fire with the right lifecycle and parents.
"""

import railtracks as rt
from railtracks.events._base import NodeParent, NoParent
from railtracks.observability import Event, configure_writers


class _Collecting:
    def __init__(self):
        self.events: list[Event] = []

    async def start(self):
        pass

    async def write(self, event: Event):
        self.events.append(event)

    async def shutdown(self):
        pass


def _by_name(events, name):
    return [e for e in events if e.payload["name"] == name]


def _types(events):
    return [e.event_type for e in events]


async def test_parent_child_lifecycle_and_parents():
    writer = _Collecting()
    configure_writers([writer])

    @rt.function_node
    def inner(x: int) -> int:
        """Inner node."""
        return x + 1

    @rt.function_node
    async def outer(x: int) -> int:
        """Outer node."""
        return await rt.call(inner, x)

    with rt.Session(flow_name="events-test"):
        result = await rt.call(outer, 10)
    assert result == 11

    outer_events = _by_name(writer.events, "outer")
    inner_events = _by_name(writer.events, "inner")

    # every node runs its full lifecycle
    for events in (outer_events, inner_events):
        assert _types(events) == [
            "node.creation",
            "node.invocation",
            "node.response",
            "node.destruction",
        ]

    # self-id is stable across an invocation's lifecycle (pairs invocation with response)
    outer_id = {e.payload["node_id"] for e in outer_events}
    inner_id = {e.payload["node_id"] for e in inner_events}
    assert len(outer_id) == 1
    assert len(inner_id) == 1
    (outer_id,) = outer_id

    # the root node has no parent; the child is parented on the caller node (no LLM, no mw)
    for e in outer_events:
        assert e.payload["parent"] == NoParent()
    for e in inner_events:
        assert e.payload["parent"] == NodeParent(node_id=outer_id, middleware_id=None)


async def test_failure_emits_node_failure_and_no_response():
    writer = _Collecting()
    configure_writers([writer])

    @rt.function_node
    def boom(x: int) -> int:
        """Explodes."""
        raise ValueError("kaboom")

    with rt.Session(flow_name="events-test"):
        try:
            await rt.call(boom, 1)
        except Exception:
            pass

    boom_events = _by_name(writer.events, "boom")
    # failure short-circuits: creation + invocation + failure, never response/destruction
    assert _types(boom_events) == ["node.creation", "node.invocation", "node.failure"]
    failure = boom_events[-1]
    assert "kaboom" in failure.payload["failure"]
