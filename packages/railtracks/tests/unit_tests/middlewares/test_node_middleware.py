"""End-to-end checks that node-level middleware actually wraps node execution.

The execution path is: rt.call -> Task.invoke -> node.wrapped_invoke -> middleware.run(invoke).
These tests prove the chain holds for function nodes built via the parametrized
decorator form (`@rt.function_node(middleware=[...])`).
"""

import asyncio

import railtracks as rt


def test_function_node_middleware_runs():
    events = []

    @rt.middleware
    async def tracing(call, *args, **kwargs):
        events.append("before")
        result = await call(*args, **kwargs)
        events.append("after")
        return result

    @rt.function_node(middleware=[tracing])
    def add(a: int, b: int) -> int:
        """Add two numbers."""
        return a + b

    async def top_level():
        with rt.Session():
            return await rt.call(add, 1, 2)

    result = asyncio.run(top_level())
    assert result == 3
    assert events == ["before", "after"]


def test_function_node_middleware_can_short_circuit():
    @rt.middleware
    async def block(call, *args, **kwargs):
        return -1

    @rt.function_node(middleware=[block])
    def add(a: int, b: int) -> int:
        """Add two numbers."""
        return a + b

    async def top_level():
        with rt.Session():
            return await rt.call(add, 1, 2)

    assert asyncio.run(top_level()) == -1
