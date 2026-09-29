"""Context events: the RAILTRACKS_CONTEXT_EVENTS level, and real Flows asserting what
gets emitted."""

import threading

import pytest
import railtracks as rt
import railtracks.events.context as context_events
from railtracks.built_nodes.llm.response import StringResponse
from railtracks.events.context import ContextEventsLevel as Level
from railtracks.llm import MessageHistory, SystemMessage
from railtracks.llm.message import AssistantMessage, UserMessage
from railtracks.observability import Event, configure_writers
from railtracks.prebuilt.middleware import ContextInjection, ConversationMemory


class _Collecting:
    def __init__(self):
        self.events: list[Event] = []

    async def start(self):
        pass

    async def write(self, event: Event):
        self.events.append(event)

    async def shutdown(self):
        pass


@pytest.fixture(autouse=True)
def _default_level(monkeypatch):
    monkeypatch.delenv("RAILTRACKS_CONTEXT_EVENTS", raising=False)


def _of_type(events, event_type):
    return [e for e in events if e.event_type == event_type]


def _context_types(events):
    return [e.event_type for e in events if e.event_type.startswith("context.")]


def _run(node, *args, context=None, **flow_kwargs):
    writer = _Collecting()
    configure_writers([writer])
    result = rt.Flow("ctx-test", node, context=context, **flow_kwargs).invoke(*args)
    return result, writer.events


def _exercise() -> str:
    rt.context.put("colour", "green")
    rt.context.update({"size": 3})
    got = rt.context.get("colour")
    rt.context.delete("size")
    rt.context.keys()
    return got


_EVERY_OP = [
    "context.creation",
    "context.put",
    "context.update",
    "context.get",
    "context.delete",
    "context.completion",
]


async def test_async_node_records_every_op():
    @rt.function_node
    async def node(_: str) -> str:
        """Exercise the context API from an async body."""
        return _exercise()

    _, events = _run(node, "x")
    assert _context_types(events) == _EVERY_OP


async def test_sync_node_records_every_op():
    @rt.function_node
    def node(_: str) -> str:
        """Exercise the context API from a sync body, which runs off the loop."""
        return _exercise()

    _, events = _run(node, "x")
    assert _context_types(events) == _EVERY_OP


async def test_payloads():
    @rt.function_node
    def node(_: str) -> str:
        """Exercise the context API."""
        return _exercise()

    _, events = _run(node, "x")

    (put,) = _of_type(events, "context.put")
    (update,) = _of_type(events, "context.update")
    (get,) = _of_type(events, "context.get")
    (delete,) = _of_type(events, "context.delete")
    assert (put.payload["keys"], put.payload["values"]) == (
        ["colour"],
        {"colour": "green"},
    )
    assert (update.payload["keys"], update.payload["values"]) == (["size"], {"size": 3})
    assert (get.payload["keys"], get.payload["values"]) == (
        ["colour"],
        {"colour": "green"},
    )
    assert (delete.payload["keys"], delete.payload["values"]) == (["size"], None)


async def test_get_records_the_default_it_returned():
    @rt.function_node
    def node(_: str) -> str:
        """Read a missing key with a default."""
        return rt.context.get("absent", default="fallback")

    result, events = _run(node, "x")

    assert result == "fallback"
    (get,) = _of_type(events, "context.get")
    assert get.payload["values"] == {"absent": "fallback"}


async def test_failed_get_and_delete_record_nothing():
    @rt.function_node
    def node(_: str) -> str:
        """Read and delete a missing key."""
        for op in (rt.context.get, rt.context.delete):
            with pytest.raises(KeyError):
                op("absent")
        return "done"

    _, events = _run(node, "x")

    assert _of_type(events, "context.get") == []
    assert _of_type(events, "context.delete") == []


async def test_op_in_a_node_body_is_attributed_to_the_node():
    @rt.function_node
    def node(_: str) -> str:
        """Put one key."""
        rt.context.put("k", "v")
        return "done"

    _, events = _run(node, "x")

    (put,) = _of_type(events, "context.put")
    (creation,) = _of_type(events, "node.creation")
    assert put.payload["spatial_parent_type"] == "node_and_middleware"
    assert put.payload["spatial_parent_node_id"] == creation.payload["node_id"]
    assert put.payload["spatial_parent_middleware_invoke_id"] is None


async def test_op_in_user_middleware_is_attributed_to_it():
    @rt.wrap_node
    async def putting(call, *args, **kwargs):
        rt.context.put("from_middleware", True)
        return await call(*args, **kwargs)

    @rt.function_node(middleware=[putting])
    def node(_: str) -> str:
        """Do nothing with context."""
        return "done"

    _, events = _run(node, "x")

    (put,) = _of_type(events, "context.put")
    assert put.payload["spatial_parent_type"] == "node_and_middleware"
    assert put.payload["spatial_parent_middleware_invoke_id"] is not None


async def test_op_outside_any_node_has_a_null_node_parent():
    seen = []

    def on_broadcast(item):
        rt.context.put("from_callback", item)
        seen.append(item)

    @rt.function_node
    async def node(message: str) -> str:
        """Broadcast, which the publisher loop hands to the callback."""
        await rt.broadcast(message)
        return "done"

    _, events = _run(node, "ping", broadcast_callback=on_broadcast)

    assert seen == ["ping"]
    (put,) = _of_type(events, "context.put")
    assert put.payload["spatial_parent_type"] == "node"
    assert put.payload["spatial_parent_node_id"] is None


async def test_put_records_the_value_at_the_time_of_the_call():
    @rt.function_node
    def node(_: str) -> int:
        """Put a list, then keep editing it."""
        cart = ["apple"]
        rt.context.put("cart", cart)
        cart.append("pear")
        return len(cart)

    _, events = _run(node, "x")

    (put,) = _of_type(events, "context.put")
    (completion,) = _of_type(events, "context.completion")
    assert put.payload["values"] == {"cart": ["apple"]}
    assert completion.payload["values"]["cart"] == ["apple", "pear"]


async def test_a_node_that_raises_after_a_put_still_records_it():
    @rt.function_node
    def node(_: str) -> str:
        """Put, then fail."""
        rt.context.put("before_boom", 1)
        raise ValueError("boom")

    writer = _Collecting()
    configure_writers([writer])
    with pytest.raises(Exception):
        rt.Flow("ctx-boom", node).invoke("x")

    (put,) = _of_type(writer.events, "context.put")
    assert put.payload["keys"] == ["before_boom"]


async def test_unserializable_values_do_not_break_the_node():
    @rt.function_node
    def node(_: str) -> str:
        """Put values json.dumps cannot handle."""
        cyclic = {}
        cyclic["self"] = cyclic
        rt.context.put("cyclic", cyclic)
        rt.context.put("lock", threading.Lock())
        return "survived"

    result, events = _run(node, "x")

    assert result == "survived"
    cyclic, lock = _of_type(events, "context.put")
    assert cyclic.payload["values"] == {"cyclic": "<unserializable dict>"}
    assert isinstance(lock.payload["values"]["lock"], str)


async def test_large_values_are_recorded_in_full():
    big = "x" * 1_000_000

    @rt.function_node
    def node(_: str) -> int:
        """Put a large value."""
        rt.context.put("big", big)
        return 1

    _, events = _run(node, "x")

    (put,) = _of_type(events, "context.put")
    assert put.payload["values"] == {"big": big}


async def test_level_0_records_no_context_events(monkeypatch):
    monkeypatch.setenv("RAILTRACKS_CONTEXT_EVENTS", "0")
    snapshotted = []
    monkeypatch.setattr(context_events, "_snapshot", snapshotted.append)

    @rt.function_node
    def node(_: str) -> str:
        """Exercise the context API."""
        return _exercise()

    result, events = _run(node, "x", context={"start": 1})

    assert result == "green"
    assert _context_types(events) == []
    assert snapshotted == []
    assert _of_type(events, "node.creation") != []


async def test_level_1_records_keys_but_no_values(monkeypatch):
    monkeypatch.setenv("RAILTRACKS_CONTEXT_EVENTS", "1")
    snapshotted = []
    monkeypatch.setattr(context_events, "_snapshot", snapshotted.append)

    @rt.function_node
    def node(_: str) -> str:
        """Exercise the context API."""
        return _exercise()

    _, events = _run(node, "x", context={"start": 1})

    assert _context_types(events) == _EVERY_OP
    assert snapshotted == []

    (put,) = _of_type(events, "context.put")
    (get,) = _of_type(events, "context.get")
    (update,) = _of_type(events, "context.update")
    (creation,) = _of_type(events, "context.creation")
    (completion,) = _of_type(events, "context.completion")
    assert (put.payload["keys"], put.payload["values"]) == (["colour"], None)
    assert (get.payload["keys"], get.payload["values"]) == (["colour"], None)
    assert (update.payload["keys"], update.payload["values"]) == (["size"], None)
    assert (creation.payload["keys"], creation.payload["values"]) == (["start"], None)
    assert completion.payload["keys"] == ["start", "colour"]
    assert completion.payload["values"] is None
    assert creation.payload["level"] == 1


async def test_an_unrecognized_level_records_keys_and_values(monkeypatch):
    monkeypatch.setenv("RAILTRACKS_CONTEXT_EVENTS", "true")

    @rt.function_node
    def node(_: str) -> str:
        """Put one key."""
        rt.context.put("k", "v")
        return "done"

    with pytest.warns(UserWarning, match="RAILTRACKS_CONTEXT_EVENTS='true'"):
        _, events = _run(node, "x")

    (put,) = _of_type(events, "context.put")
    (creation,) = _of_type(events, "context.creation")
    assert put.payload["values"] == {"k": "v"}
    assert creation.payload["level"] == 2


def test_level_defaults_to_keys_and_values():
    assert context_events._context_events_level() is Level.KEYS_AND_VALUES


@pytest.mark.parametrize(
    "raw, level",
    [
        ("0", Level.OFF),
        ("1", Level.KEYS),
        ("2", Level.KEYS_AND_VALUES),
        (" 1 ", Level.KEYS),
    ],
)
def test_level_parses_each_value(monkeypatch, raw, level):
    monkeypatch.setenv("RAILTRACKS_CONTEXT_EVENTS", raw)
    assert context_events._context_events_level() is level


@pytest.mark.parametrize("raw", ["true", "3", "-1", "01"])
def test_level_warns_and_defaults_on_anything_else(monkeypatch, raw):
    monkeypatch.setenv("RAILTRACKS_CONTEXT_EVENTS", raw)
    with pytest.warns(UserWarning, match="RAILTRACKS_CONTEXT_EVENTS"):
        assert context_events._context_events_level() is Level.KEYS_AND_VALUES


async def test_creation_and_completion_bracket_the_run():
    @rt.function_node
    def node(_: str) -> str:
        """Add a key mid-run."""
        rt.context.put("added", "later")
        return "done"

    _, events = _run(node, "x", context={"initial": "value"})

    types = [e.event_type for e in events]
    assert types.index("session.started") < types.index("context.creation")
    assert types.index("context.completion") < types.index("session.completed")

    (creation,) = _of_type(events, "context.creation")
    (completion,) = _of_type(events, "context.completion")
    assert creation.payload["level"] == 2
    assert creation.payload["keys"] == ["initial"]
    assert creation.payload["values"] == {"initial": "value"}
    assert completion.payload["keys"] == ["initial", "added"]
    assert completion.payload["values"] == {"initial": "value", "added": "later"}


async def test_conversation_memory_records_no_context_ops():
    memory = ConversationMemory()

    async def fake_agent(_):
        return StringResponse(
            "hi", MessageHistory([UserMessage("turn"), AssistantMessage("hi")])
        )

    @rt.function_node
    async def node(user_input: str) -> str:
        """Two turns through the memory middleware, then a clear."""
        wrapped = memory.wrap(fake_agent)
        await wrapped(user_input)
        await wrapped("again")
        memory.clear()
        return "done"

    _, events = _run(node, "hello")
    assert _context_types(events) == ["context.creation", "context.completion"]


async def test_prompt_injection_records_no_context_ops():
    async def fake_call(message_history, schema, tools):
        return message_history[0].content

    @rt.function_node
    async def node(history):
        """Inject context into a prompt, one placeholder present and one absent."""
        return await ContextInjection().wrap(fake_call)(history, None, None)

    writer = _Collecting()
    configure_writers([writer])
    result = await rt.Flow("ctx-injection", node, context={"name": "Alice"}).ainvoke(
        MessageHistory([SystemMessage("Hi {name} and {absent}.")])
    )

    assert result == "Hi Alice and {absent}."
    assert _context_types(writer.events) == ["context.creation", "context.completion"]


async def test_update_accepts_any_iterable_of_pairs():
    @rt.function_node
    def node(_: str) -> int:
        """Update from a zip rather than a dict."""
        rt.context.update(zip(["a", "b"], [1, 2]))
        return rt.context.get("b")

    result, events = _run(node, "x")

    assert result == 2
    (update,) = _of_type(events, "context.update")
    assert update.payload["values"] == {"a": 1, "b": 2}


async def test_a_failed_snapshot_does_not_break_the_run(monkeypatch):
    def boom():
        raise RuntimeError("snapshot failed")

    monkeypatch.setattr(context_events, "external_context", boom)

    @rt.function_node
    def node(_: str) -> str:
        """Do nothing with context."""
        return "done"

    result, events = _run(node, "x")

    assert result == "done"
    assert _of_type(events, "context.creation") == []
    assert _of_type(events, "context.completion") == []
    (completed,) = _of_type(events, "session.completed")
    assert completed.payload["status"] == "success"


async def test_nothing_is_snapshotted_without_a_writer(monkeypatch):
    monkeypatch.setenv("RAILTRACKS_DISABLE_EVENTS", "true")
    snapshotted = []
    monkeypatch.setattr(context_events, "_snapshot", snapshotted.append)

    @rt.function_node
    def node(_: str) -> str:
        """Use every op that records a value."""
        rt.context.put("k", "v")
        rt.context.update({"k": "w"})
        return rt.context.get("k")

    result = rt.Flow("ctx-no-writer", node, context={"start": 1}).invoke("x")

    assert result == "w"
    assert snapshotted == []
