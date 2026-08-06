"""Event fields the legacy JSON session trace needs in order to be reconstructed."""

import contextlib

import railtracks as rt
import railtracks.context.central as central
from railtracks.built_nodes.llm.model_invoker import ModelInvoker
from railtracks.llm.history import MessageHistory
from railtracks.llm.message import Message, Role
from railtracks.llm.response import MessageInfo, Response
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


class _FakeModel:
    """`model_name()` returns the routing slug; the response echoes back the bare name
    the provider reported, mirroring the real split between the two."""

    id = "llm-1"

    def __init__(
        self,
        echoed_name: str | None = "claude-sonnet-4-6",
        raises: Exception | None = None,
    ):
        self._echoed_name = echoed_name
        self._raises = raises

    def model_name(self):
        return "anthropic/claude-sonnet-4-6"

    def model_provider(self):
        return "Anthropic"

    def chat(self, messages):
        if self._raises is not None:
            raise self._raises
        return Response(
            message=Message(role=Role.assistant, content="hi"),
            message_info=MessageInfo(model_name=self._echoed_name),
        )


def _register(session_id="sess-1"):
    central.register_globals(
        session_id=session_id,
        rt_publisher=None,
        executor_config=ExecutorConfig(),
        global_context_vars={},
    )


async def _run_model_invoker(model: _FakeModel) -> list[Event]:
    writer = _Collecting()
    configure_writers([writer])
    await ensure_started()
    invoker = ModelInvoker.create_with_llm_observe(
        model, get_scope_manager=central.ContextVarScopeManager
    )
    with central.ContextVarScopeManager().enter_node("node-1"):
        with contextlib.suppress(Exception):  # the failure path re-raises by design
            await invoker.invoke(MessageHistory())
    await shutdown()  # drains the writer queue so delivery is deterministic
    return writer.events


def _of_type(events: list[Event], event_type: str) -> list[Event]:
    return [e for e in events if e.event_type == event_type]


async def test_llm_response_carries_the_provider_reported_model_name():
    """The legacy trace recorded the unprefixed name, so prefer what the provider echoed."""
    _register()
    events = await _run_model_invoker(_FakeModel())

    responses = _of_type(events, "llm.response")
    assert len(responses) == 1
    payload = responses[0].payload
    assert payload["model_name"] == "claude-sonnet-4-6"
    assert payload["model_provider"] == "Anthropic"


async def test_llm_response_falls_back_to_the_model_name_when_none_reported():
    """Not every provider echoes a name back; the routing slug is better than nothing."""
    _register()
    events = await _run_model_invoker(_FakeModel(echoed_name=None))

    payload = _of_type(events, "llm.response")[0].payload
    assert payload["model_name"] == "anthropic/claude-sonnet-4-6"
    assert payload["model_provider"] == "Anthropic"


async def test_llm_failure_carries_the_model_identity():
    """The legacy trace recorded a failed call as an entry too, model and all."""
    _register()
    events = await _run_model_invoker(_FakeModel(raises=RuntimeError("boom")))

    failures = _of_type(events, "llm.failure")
    assert len(failures) == 1
    payload = failures[0].payload
    assert payload["model_name"] == "anthropic/claude-sonnet-4-6"
    assert payload["model_provider"] == "Anthropic"
    assert payload["exception_name"] == "RuntimeError"
    assert _of_type(events, "llm.response") == []


async def test_node_destruction_carries_a_duration():
    """`internals.latency.total_time` is rebuilt from this field."""
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

    with rt.Session(flow_name="duration-test"):
        assert await rt.call(outer, 10) == 11

    names = {
        e.payload["node_id"]: e.payload["name"]
        for e in writer.events
        if e.event_type == "node.creation"
    }
    # a node event's `parent` is the node itself; `spatial_parent` is its caller
    durations = {
        names[e.payload["parent_node_id"]]: e.payload["duration_seconds"]
        for e in _of_type(writer.events, "node.destruction")
    }

    assert set(durations) == {"outer", "inner"}
    assert all(d > 0 for d in durations.values())
    # outer wraps the call to inner, so it cannot be the shorter of the two
    assert durations["outer"] >= durations["inner"]
