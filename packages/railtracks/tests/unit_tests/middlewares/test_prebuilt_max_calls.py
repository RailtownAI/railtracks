"""Unit tests for the prebuilt MaxCalls middleware."""

from __future__ import annotations

import pytest
from railtracks.middleware import Middleware
from railtracks.prebuilt.middleware.max_calls import MaxCalls, MaxCallsExceededError


def test_max_calls_is_a_plain_middleware():
    assert isinstance(MaxCalls(1), Middleware)


def test_max_calls_exceeded_error_is_exported_flat():
    from railtracks.prebuilt.middleware import MaxCallsExceededError as PublicError

    assert PublicError is MaxCallsExceededError


@pytest.mark.asyncio
async def test_calls_within_the_limit_succeed():
    async def add(x, *, y):
        return x + y

    max_calls = MaxCalls(2)

    assert await max_calls.wrap(add)(2, y=3) == 5
    assert await max_calls.wrap(add)(4, y=5) == 9


@pytest.mark.asyncio
async def test_call_beyond_the_limit_raises():
    async def add(x, y):
        return x + y

    max_calls = MaxCalls(1)
    await max_calls.wrap(add)(1, 2)

    with pytest.raises(MaxCallsExceededError, match="Maximum number of calls exceeded"):
        await max_calls.wrap(add)(1, 2)


@pytest.mark.asyncio
async def test_custom_message_is_used_when_limit_exceeded():
    async def noop():
        return None

    max_calls = MaxCalls(0, custom_message="budget exhausted")

    with pytest.raises(MaxCallsExceededError, match="budget exhausted"):
        await max_calls.wrap(noop)()


@pytest.mark.asyncio
async def test_count_is_not_incremented_once_limit_is_hit():
    async def noop():
        return None

    max_calls = MaxCalls(0)

    for _ in range(3):
        with pytest.raises(
            MaxCallsExceededError, match="Maximum number of calls exceeded"
        ):
            await max_calls.wrap(noop)()

    assert max_calls.call_count == 0


@pytest.mark.asyncio
async def test_wrapped_exception_propagates_and_still_counts_the_call():
    async def broken():
        raise ValueError("broken")

    max_calls = MaxCalls(2)

    with pytest.raises(ValueError, match="broken"):
        await max_calls.wrap(broken)()

    assert max_calls.call_count == 1


def test_node_middleware_slot_enforces_limit_inside_single_run():
    import railtracks as rt

    @rt.function_node(middleware=[MaxCalls(2, custom_message="tool budget hit")])
    def limited(x: str) -> str:
        return x

    @rt.function_node
    async def driver(n: int) -> list[str]:
        out = []
        for i in range(n):
            try:
                out.append(await rt.call(limited, x=str(i)))
            except Exception as e:
                out.append(type(e).__name__)
        return out

    flow = rt.Flow("node-slot-repro", entry_point=driver)
    results = flow.invoke(n=4)
    assert results == ["0", "1", "MaxCallsExceededError", "MaxCallsExceededError"]


def test_node_middleware_slot_starts_fresh_on_subsequent_run():
    import railtracks as rt

    @rt.function_node(middleware=[MaxCalls(2, custom_message="tool budget hit")])
    def limited(x: str) -> str:
        return x

    @rt.function_node
    async def driver(n: int) -> list[str]:
        out = []
        for i in range(n):
            try:
                out.append(await rt.call(limited, x=str(i)))
            except Exception as e:
                out.append(type(e).__name__)
        return out

    flow = rt.Flow("node-slot-fresh-run", entry_point=driver)
    assert flow.invoke(n=2) == ["0", "1"]
    assert flow.invoke(n=2) == ["0", "1"]


def test_multiple_nodes_share_combined_budget():
    import railtracks as rt

    shared_budget = MaxCalls(3, custom_message="shared cap hit")

    @rt.function_node(middleware=[shared_budget])
    def tool_a(x: str) -> str:
        return f"A:{x}"

    @rt.function_node(middleware=[shared_budget])
    def tool_b(x: str) -> str:
        return f"B:{x}"

    @rt.function_node
    async def driver() -> list[str]:
        out = []
        for f, arg in [(tool_a, "1"), (tool_a, "2"), (tool_b, "3"), (tool_b, "4")]:
            try:
                out.append(await rt.call(f, x=arg))
            except Exception as e:
                out.append(type(e).__name__)
        return out

    flow = rt.Flow("shared-budget-flow", entry_point=driver)
    assert flow.invoke() == ["A:1", "A:2", "B:3", "MaxCallsExceededError"]
    assert flow.invoke() == ["A:1", "A:2", "B:3", "MaxCallsExceededError"]


@pytest.mark.asyncio
async def test_call_count_property_and_reset():
    async def noop():
        return None

    max_calls = MaxCalls(3)
    assert max_calls.call_count == 0

    await max_calls.wrap(noop)()
    await max_calls.wrap(noop)()
    assert max_calls.call_count == 2

    max_calls.reset()
    assert max_calls.call_count == 0

    await max_calls.wrap(noop)()
    assert max_calls.call_count == 1


def test_agent_node_middleware_slot_enforces_limit(mock_llm):
    import railtracks as rt

    agent = rt.agent_node(
        "Agent",
        llm=mock_llm(custom_response="hello"),
        middleware=[MaxCalls(2, custom_message="agent limit hit")],
    )

    @rt.function_node
    async def driver(n: int) -> list[str]:
        out = []
        for i in range(n):
            try:
                res = await rt.call(agent, user_input=f"query {i}")
                out.append(res.content)
            except Exception as e:
                out.append(type(e).__name__)
        return out

    flow = rt.Flow("agent-node-slot", entry_point=driver)
    results = flow.invoke(n=3)
    assert results == ["hello", "hello", "MaxCallsExceededError"]


def test_lock_middleware_shared_across_nodes_preserves_reference():
    """Lock instances survive Node.safe_copy() via MiddlewareChain.__deepcopy__."""
    import railtracks as rt
    from railtracks.prebuilt.middleware.lock import Lock

    shared_lock = Lock()

    @rt.function_node(middleware=[shared_lock])
    def t1(x: int) -> int:
        return x

    @rt.function_node(middleware=[shared_lock])
    def t2(x: int) -> int:
        return x

    node1 = t1.node_type()
    node2 = t2.node_type()

    # safe_copy must preserve the Lock reference
    copied_node = node1.safe_copy()
    assert copied_node.middleware.middleware[0] is shared_lock

    # Both nodes share the same Lock
    assert node1.middleware.middleware[0] is node2.middleware.middleware[0]


def test_concurrent_sessions_get_independent_budgets():
    """Two concurrent runs sharing a MaxCalls instance get independent counters."""
    import railtracks as rt

    shared = MaxCalls(2, custom_message="cap hit")

    @rt.function_node(middleware=[shared])
    def tool(x: str) -> str:
        return x

    @rt.function_node
    async def driver(n: int) -> list[str]:
        out = []
        for i in range(n):
            try:
                out.append(await rt.call(tool, x=str(i)))
            except Exception as e:
                out.append(type(e).__name__)
        return out

    flow_a = rt.Flow("session-a", entry_point=driver)
    flow_b = rt.Flow("session-b", entry_point=driver)

    # Each flow gets its own session, so each gets a fresh budget of 2
    assert flow_a.invoke(n=3) == ["0", "1", "MaxCallsExceededError"]
    assert flow_b.invoke(n=3) == ["0", "1", "MaxCallsExceededError"]
