"""rt.context.local: session-scoped state owned by the running middleware or node."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field

import pytest
import railtracks as rt
import railtracks.context.central as central
from railtracks.exceptions import ContextError
from railtracks.middleware import Middleware
from railtracks.utils.config import ExecutorConfig


@dataclass
class Counter:
    calls: int = 0


@dataclass
class Seen:
    values: list[str] = field(default_factory=list)


def count_calls() -> Middleware:
    @rt.wrap_node
    async def counter(call, *args, **kwargs):
        rt.context.local(Counter).calls += 1
        return await call(*args, **kwargs)

    return counter


class CountCalls(Middleware):
    def __init__(self):
        super().__init__(self._middleware_fn)

    @property
    def calls(self) -> int:
        return rt.context.local(Counter, owner=self).calls

    async def _middleware_fn(self, call, *args, **kwargs):
        rt.context.local(Counter).calls += 1
        return await call(*args, **kwargs)


@rt.function_node
async def stateful_tool() -> int:
    await asyncio.sleep(0)
    state = rt.context.local(Counter)
    state.calls += 1
    return state.calls


# ================================ tools ================================


def test_tool_state_starts_fresh_in_every_session():
    @rt.function_node
    async def driver(n: int) -> list[int]:
        return [await rt.call(stateful_tool) for _ in range(n)]

    flow = rt.Flow("fresh-sessions", entry_point=driver)

    assert flow.invoke(n=3) == [1, 2, 3]
    assert flow.invoke(n=2) == [1, 2]


def test_concurrent_sessions_keep_separate_state():
    @rt.function_node
    async def driver(n: int) -> int:
        last = 0
        for _ in range(n):
            last = await rt.call(stateful_tool)
        return last

    async def run_both():
        return await asyncio.gather(
            rt.Flow("concurrent-a", entry_point=driver).ainvoke(n=3),
            rt.Flow("concurrent-b", entry_point=driver).ainvoke(n=5),
        )

    assert asyncio.run(run_both()) == [3, 5]


def test_two_tools_keep_separate_state():
    @rt.function_node
    def other_tool() -> int:
        state = rt.context.local(Counter)
        state.calls += 10
        return state.calls

    @rt.function_node
    async def driver() -> list[int]:
        return [
            await rt.call(stateful_tool),
            await rt.call(other_tool),
            await rt.call(stateful_tool),
        ]

    assert rt.Flow("two-tools", entry_point=driver).invoke() == [1, 10, 2]


def test_coupled_tool_shares_state_with_the_original():
    coupled = rt.couple(stateful_tool, middleware=[count_calls()])

    @rt.function_node
    async def driver() -> list[int]:
        return [await rt.call(stateful_tool), await rt.call(coupled)]

    assert rt.Flow("coupled-tool", entry_point=driver).invoke() == [1, 2]


def test_one_owner_keeps_one_value_per_class():
    @rt.function_node
    def tool(x: str) -> tuple[int, list[str]]:
        counter = rt.context.local(Counter)
        seen = rt.context.local(Seen)
        counter.calls += 1
        seen.values.append(x)
        return counter.calls, list(seen.values)

    @rt.function_node
    async def driver() -> tuple[int, list[str]]:
        await rt.call(tool, x="a")
        return await rt.call(tool, x="b")

    assert rt.Flow("two-classes", entry_point=driver).invoke() == (2, ["a", "b"])


def test_state_is_not_part_of_the_context_dictionary():
    @rt.function_node
    def tool() -> list[str]:
        rt.context.local(Counter).calls += 1
        return list(rt.context.keys())

    assert rt.Flow("not-in-context", entry_point=tool).invoke() == []


# ============================== middleware ==============================


def test_decorator_middleware_owns_its_state_and_shares_it_across_nodes():
    counter = count_calls()

    @rt.function_node(middleware=[counter])
    def tool_a() -> str:
        return "a"

    @rt.function_node(middleware=[counter])
    def tool_b() -> str:
        return "b"

    @rt.function_node
    async def driver() -> int:
        await rt.call(tool_a)
        await rt.call(tool_b)
        await rt.call(tool_a)
        return rt.context.local(Counter, owner=counter).calls

    flow = rt.Flow("decorator-shared", entry_point=driver)

    assert flow.invoke() == 3
    assert flow.invoke() == 3


def test_two_instances_of_one_middleware_keep_separate_state():
    first, second = CountCalls(), CountCalls()

    @rt.function_node(middleware=[first])
    def tool_a() -> str:
        return "a"

    @rt.function_node(middleware=[second])
    def tool_b() -> str:
        return "b"

    @rt.function_node
    async def driver() -> tuple[int, int]:
        await rt.call(tool_a)
        await rt.call(tool_a)
        await rt.call(tool_b)
        return first.calls, second.calls

    assert rt.Flow("two-instances", entry_point=driver).invoke() == (2, 1)


def test_middleware_and_the_node_it_wraps_have_separate_owners():
    counter = CountCalls()
    wrapped = rt.couple(stateful_tool, middleware=[counter])

    @rt.function_node
    async def driver() -> tuple[int, int]:
        await rt.call(wrapped)
        await rt.call(wrapped)
        tool_calls = await rt.call(stateful_tool)
        return tool_calls, counter.calls

    assert rt.Flow("separate-owners", entry_point=driver).invoke() == (3, 2)


# ============================ outside a run ============================


def test_outside_a_session_raises_context_error():
    with pytest.raises(ContextError):
        rt.context.local(Counter)


def test_inside_a_session_without_an_owner_raises_context_error():
    central.register_globals(
        session_id="no-owner",
        rt_publisher=None,
        executor_config=ExecutorConfig(),
        global_context_vars={},
    )
    try:
        with pytest.raises(ContextError):
            rt.context.local(Counter)
        assert rt.context.local(Counter, owner=CountCalls()).calls == 0
    finally:
        central.delete_globals()


def test_restore_scope_keeps_the_session_state():
    central.register_globals(
        session_id="restore",
        rt_publisher=None,
        executor_config=ExecutorConfig(),
        global_context_vars={},
    )
    try:
        state = central.get_owned_state(Counter, "owner")
        with central.restore_scope(None, None):
            assert central.get_owned_state(Counter, "owner") is state
    finally:
        central.delete_globals()
