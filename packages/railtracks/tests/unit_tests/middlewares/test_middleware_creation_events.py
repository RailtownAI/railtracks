"""A middleware announces itself once per session, however often it runs or is shared.

Session documents resolve middleware names (e.g. a guardrail's ``rail_name``) from the
``middleware.creation`` events of that session only, so a shared instance has to emit
one in every run it takes part in.
"""

import asyncio
from collections import Counter

import pytest
import railtracks as rt
import railtracks.middleware.core as core
from railtracks.context.central import get_session_id
from railtracks.events.middleware import MiddlewareCreationEvent
from railtracks.middleware import wrap_node
from railtracks.prebuilt.middleware.max_calls import MaxCalls


@pytest.fixture
def creations(monkeypatch) -> list[tuple[str, str]]:
    """Every (session id, middleware type id) pair a creation event is emitted for."""
    seen: list[tuple[str, str]] = []
    emit = core.emit

    async def record(event):
        if isinstance(event, MiddlewareCreationEvent):
            seen.append((get_session_id(), event.middleware_type_id))
        await emit(event)

    monkeypatch.setattr(core, "emit", record)
    return seen


def _per_session(seen: list[tuple[str, str]], type_id: str) -> list[int]:
    counts = Counter(session for session, tid in seen if tid == type_id)
    return list(counts.values())


@wrap_node
async def _passthrough(call, *args, **kwargs):
    return await call(*args, **kwargs)


def test_shared_node_middleware_announces_itself_once_in_every_run(creations):
    budget = MaxCalls(10)

    @rt.function_node(middleware=[budget])
    def tool(x: str) -> str:
        return x

    @rt.function_node
    async def driver() -> list[str]:
        return [await rt.call(tool, x=str(i)) for i in range(3)]

    flow = rt.Flow("node-mw-creation", entry_point=driver)
    flow.invoke()
    flow.invoke()

    assert _per_session(creations, budget.type_id) == [1, 1]


def test_shared_model_middleware_announces_itself_once_in_every_run(
    creations, mock_llm
):
    @rt.wrap_llm
    async def tracer(call, message_history, schema, tools):
        return await call(message_history, schema, tools)

    agent = rt.agent_node(
        "Agent", llm=mock_llm(custom_response="hi"), model_middleware=[tracer]
    )

    @rt.function_node
    async def driver() -> list[str]:
        return [(await rt.call(agent, user_input="q")).content for _ in range(2)]

    flow = rt.Flow("model-mw-creation", entry_point=driver)
    flow.invoke()
    flow.invoke()

    assert _per_session(creations, tracer.type_id) == [1, 1]


def test_concurrent_runs_each_get_their_own_announcement(creations):
    @rt.function_node(middleware=[_passthrough])
    async def tool(x: str) -> str:
        await asyncio.sleep(0)
        return x

    async def run_both():
        flow_a = rt.Flow("concurrent-a", entry_point=tool)
        flow_b = rt.Flow("concurrent-b", entry_point=tool)
        return await asyncio.gather(flow_a.ainvoke(x="a"), flow_b.ainvoke(x="b"))

    assert asyncio.run(run_both()) == ["a", "b"]
    assert _per_session(creations, _passthrough.type_id) == [1, 1]


def test_coupled_and_original_node_share_one_announcement_per_run(creations):
    @rt.function_node(middleware=[_passthrough])
    def tool(x: str) -> str:
        return x

    coupled = rt.couple(tool, middleware=[MaxCalls(10)])

    @rt.function_node
    async def driver() -> list[str]:
        return [await rt.call(tool, x="a"), await rt.call(coupled, x="b")]

    assert rt.Flow("coupled-creation", entry_point=driver).invoke() == ["a", "b"]
    assert _per_session(creations, _passthrough.type_id) == [1]


@pytest.mark.asyncio
async def test_announcing_outside_a_session_does_not_use_up_the_first_run(creations):
    budget = MaxCalls(10)

    # nothing can observe an announcement outside a session, so none is made
    await budget.start_creation_task()
    assert creations == []

    @rt.function_node(middleware=[budget])
    def tool(x: str) -> str:
        return x

    assert await rt.Flow("after-outside", entry_point=tool).ainvoke(x="a") == "a"
    assert _per_session(creations, budget.type_id) == [1]
