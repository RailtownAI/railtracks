"""End-to-end checks that node-level middleware actually wraps node execution.

The execution path is: rt.call -> Task.invoke -> node.wrapped_invoke -> middleware.run(invoke).
These tests prove the chain holds for function nodes built via the parametrized
decorator form (`@rt.function_node(middleware=[...])`).
"""

import asyncio

import pytest
import railtracks as rt
from railtracks.prebuilt.middleware import MaxCalls, Retry, Timeout


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

    @rt.function_node(middleware=[rt.post_node(mark)])
    def boom() -> int:
        raise ValueError("nope")

    async def top_level():
        with rt.Session():
            return await rt.call(boom)

    with pytest.raises(ValueError, match="nope"):
        asyncio.run(top_level())
    assert fn_called["value"] is False


def test_after_replaces_return_value_on_success():
    @rt.function_node(middleware=[rt.post_node(lambda result: result * 10)])
    def five() -> int:
        return 5

    async def top_level():
        with rt.Session():
            return await rt.call(five)

    assert asyncio.run(top_level()) == 50


def test_multiple_prebuilt_middleware_in_one_list():
    """Two prebuilt middleware in a single middleware= list must not collapse
    _P to Never.  Regression for #1538: Retry, Timeout, and MaxCalls all
    subclassed the bare Middleware generic, which mypy resolved as
    Middleware[Never, Never] under invariant generics, breaking list-element
    unification when combining any two of them."""

    @rt.function_node(middleware=[Retry(max_tries=1), Timeout(seconds=5)])
    def add(x: str) -> str:
        return x

    async def top_level():
        with rt.Session():
            return await rt.call(add, "hello")

    assert asyncio.run(top_level()) == "hello"


def test_three_different_prebuilt_middleware_in_one_list():
    """Combining three distinct prebuilt middleware in one list must work both
    at runtime and under static analysis (no Never collapse)."""

    @rt.function_node(
        middleware=[Retry(max_tries=1), Timeout(seconds=5), MaxCalls(max_calls=3)]
    )
    def echo(x: int) -> int:
        return x

    async def top_level():
        with rt.Session():
            return await rt.call(echo, 42)

    assert asyncio.run(top_level()) == 42


def test_decorator_factory_form_preserves_signature():
    """The parametrized-decorator form must pass the decorated function's
    signature through to the returned RTFunction unchanged.

    This is the runtime-observable half of the 'no Never collapse' contract:
    if _P were collapsed to Never the node call below would fail at runtime
    because the wrapped call would receive the wrong argument shape.
    """

    @rt.function_node(middleware=[Retry(max_tries=1), MaxCalls(max_calls=5)])
    def greet(name: str, times: int) -> str:
        """Greet someone.

        Args:
            name: who to greet
            times: repetition count
        """
        return (name + " ") * times

    async def top_level():
        with rt.Session():
            return await rt.call(greet, "hi", 3)

    assert asyncio.run(top_level()) == "hi hi hi "
    # Verify the LLM-facing tool info preserves the original parameter names.
    params = {p.name for p in greet.node_type.tool_info().parameters}
    assert params == {"name", "times"}, (
        "Decorator-factory form collapsed _P: parameter names were lost"
    )


def test_prebuilt_middleware_does_not_constrain_function_signature():
    """Slot-agnostic prebuilt middleware (Middleware[Any, Any]) must impose no
    constraint on the decorated function's signature -- verified by using two
    structurally different functions with the same middleware list.

    If the middleware list constrained _P, mypy/pyright would infer the
    intersection of both functions' signatures, narrowing at least one to Never.
    The runtime proxy of that inference is that rt.call would reject the call
    or the node would drop parameters; this test catches both.
    """

    @rt.function_node(middleware=[Retry(max_tries=1), Timeout(seconds=5)])
    def int_fn(x: int) -> int:
        return x * 2

    @rt.function_node(middleware=[Retry(max_tries=1), Timeout(seconds=5)])
    def str_fn(label: str, count: int) -> str:
        return label * count

    async def top_level():
        with rt.Session():
            a = await rt.call(int_fn, 7)
            b = await rt.call(str_fn, "x", 3)
            return a, b

    a, b = asyncio.run(top_level())
    assert a == 14
    assert b == "xxx"
