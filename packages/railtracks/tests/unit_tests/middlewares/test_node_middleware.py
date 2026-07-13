"""End-to-end checks that node-level middleware actually wraps node execution.

The execution path is: rt.call -> Task.invoke -> node.wrapped_invoke -> middleware.run(invoke).
These tests prove the chain holds for function nodes built via the parametrized
decorator form (`@rt.function_node(middleware=[...])`).
"""

import asyncio

import pytest
import railtracks as rt


def test_function_node_middleware_runs():
    events = []

    @rt.wrap_node
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
    @rt.wrap_node
    async def block(call, *args, **kwargs) -> int:
        return -1

    @rt.function_node(middleware=[block])
    def add(a: int, b: int) -> int:
        """Add two numbers."""
        return a + b
    
    node = add.node_type()

    print(node.invoke(1, 2))
    print(node.wrapped_invoke(1, 2))

    async def top_level():
        with rt.Session():
            return await rt.call(add, 1, 2)

    assert asyncio.run(top_level()) == -1


def test_middleware_exception_propagates_through_multiple_layers():
    log = []

    @rt.wrap_node
    async def outer(call, *args, **kwargs):
        log.append("outer-in")
        try:
            return await call(*args, **kwargs)
        finally:
            log.append("outer-out")

    @rt.wrap_node
    async def inner(call, *args, **kwargs):
        log.append("inner-in")
        try:
            return await call(*args, **kwargs)
        finally:
            log.append("inner-out")

    @rt.function_node(middleware=[outer, inner])
    def boom(a: int, b: int) -> int:
        raise ValueError("kaboom")

    async def top_level():
        with rt.Session():
            return await rt.call(boom, 1, 2)

    with pytest.raises(ValueError, match="kaboom"):
        asyncio.run(top_level())
    assert log == ["outer-in", "inner-in", "inner-out", "outer-out"]


def test_multiple_middleware_outer_to_inner_order():
    log = []

    @rt.wrap_node
    async def first(call, *args, **kwargs):
        log.append("first-in")
        result = await call(*args, **kwargs)
        log.append("first-out")
        return result

    @rt.wrap_node
    async def second(call, *args, **kwargs):
        log.append("second-in")
        result = await call(*args, **kwargs)
        log.append("second-out")
        return result

    @rt.function_node(middleware=[first, second])
    def identity(x: int) -> int:
        log.append("core")
        return x

    async def top_level():
        with rt.Session():
            return await rt.call(identity, 5)

    result = asyncio.run(top_level())
    assert result == 5
    assert log == ["first-in", "second-in", "core", "second-out", "first-out"]


def test_after_does_not_run_when_call_raises():
    fn_called = {"value": False}

    def mark(result):
        fn_called["value"] = True
        return result

    @rt.function_node(middleware=[rt.after_node(mark)])
    def boom() -> int:
        raise ValueError("nope")

    async def top_level():
        with rt.Session():
            return await rt.call(boom)

    with pytest.raises(ValueError, match="nope"):
        asyncio.run(top_level())
    assert fn_called["value"] is False


def test_after_replaces_return_value_on_success():
    @rt.function_node(middleware=[rt.after_node(lambda result: result * 10)])
    def five() -> int:
        return 5

    async def top_level():
        with rt.Session():
            return await rt.call(five)

    assert asyncio.run(top_level()) == 50
