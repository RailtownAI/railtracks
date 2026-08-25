"""Hot-path integration: run a real node graph and assert the emitted node events.

Unlike `test_send.py` (which drives `pipe` directly against a synthetic scope), this runs
`rt.call` end-to-end and checks that the emission sites in `nodes.py`,
`_node_builder.py`, and `state.py` fire with the right lifecycle and relationships.

Only `node.creation` carries the node's name/id; the running events identify themselves
through the resolved `parent` (which, for a node event, is the node itself).
"""

import railtracks as rt
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


def _node_events(events):
    return [e for e in events if e.event_type.startswith("node.")]


def _ids_by_name(events):
    """node name -> node_id, read off the creation events."""
    return {
        e.payload["name"]: e.payload["node_id"]
        for e in events
        if e.event_type == "node.creation"
    }


def _lifecycle(events, *, name, node_id):
    """The ordered event types belonging to one node."""
    out = []
    for e in _node_events(events):
        if e.event_type == "node.creation":
            if e.payload["name"] == name:
                out.append(e.event_type)
        elif e.payload["parent_node_id"] == node_id:
            out.append(e.event_type)
    return out


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

    ids = _ids_by_name(writer.events)
    assert set(ids) == {"outer", "inner"}

    # every node runs its full lifecycle
    for name, node_id in ids.items():
        assert _lifecycle(writer.events, name=name, node_id=node_id) == [
            "node.creation",
            "node.invocation",
            "node.response",
            "node.destruction",
        ]

    # the root node has no enclosing node; the child is nested inside the caller
    running = [
        e for e in _node_events(writer.events) if e.event_type != "node.creation"
    ]
    for e in running:
        enclosing = e.payload["spatial_parent_node_id"]
        if e.payload["parent_node_id"] == ids["outer"]:
            assert enclosing is None
        else:
            assert enclosing == ids["outer"]


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

    ids = _ids_by_name(writer.events)
    lifecycle = _lifecycle(writer.events, name="boom", node_id=ids["boom"])
    # failure replaces the response; destruction still fires as the node unwinds
    assert lifecycle == [
        "node.creation",
        "node.invocation",
        "node.failure",
        "node.destruction",
    ]

    failure = [e for e in writer.events if e.event_type == "node.failure"][0]
    assert "kaboom" in failure.payload["exception_message"]
