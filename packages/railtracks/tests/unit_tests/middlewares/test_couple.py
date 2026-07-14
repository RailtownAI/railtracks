"""Unit tests for `couple` -- post-hoc middleware attachment.

`couple(node, *middleware)` works on either a `type[Node]` (returns a new subclass
via `Node.extend_middleware`, original class untouched) or an RTFunction / function
node (returns a new wrapper via `with_node_type`, sharing the same underlying
callable but with its own, independently-extended `node_type` -- the original
RTFunction is never modified). Neither branch mutates what was passed in: calling
`couple()` again against the same original always starts from that original's
pristine state, so composing requires chaining off the previous result rather than
calling `couple()` repeatedly against the same base.
"""

import asyncio

import railtracks as rt
from railtracks.interaction import couple
from railtracks.middleware import wrap_node


def _make_node():
    @rt.function_node
    def add(a: int, b: int) -> int:
        return a + b

    return add


def _tracer(label, log):
    @wrap_node
    async def m(call, *args, **kwargs):
        log.append(f"{label}-in")
        result = await call(*args, **kwargs)
        log.append(f"{label}-out")
        return result

    return m


async def _run(node, *args):
    flow = rt.Flow("Test Flow", node)
    return await flow.ainvoke(*args)


def test_couple_on_node_type_returns_new_subclass():
    fn = _make_node()
    original_cls = fn.node_type
    mw = _tracer("m", [])

    new_cls = couple(original_cls, mw)

    assert new_cls is not original_cls
    assert issubclass(new_cls, original_cls)
    assert original_cls._user_middleware == []
    assert new_cls._user_middleware == [mw]


def test_couple_on_rt_function_does_not_mutate_node_type_in_place():
    fn = _make_node()
    original_node_type = fn.node_type
    mw = _tracer("m", [])

    result = couple(fn, mw)

    assert result is not fn
    assert result.node_type is not original_node_type
    assert result.node_type._user_middleware == [mw]

    # the original is untouched: same node_type object, no middleware attached
    assert fn.node_type is original_node_type
    assert fn.node_type._user_middleware == []


def test_couple_on_rt_function_shares_underlying_callable():
    """`couple()` never deep-copies the underlying function -- a real function
    object can't be independently copied (CPython treats it as atomic), so the new
    wrapper shares the exact same `.func` as the original instead."""
    fn = _make_node()
    result = couple(fn, _tracer("m", []))

    assert result.func is fn.func


def test_couple_on_rt_function_preserves_name():
    fn = _make_node()
    result = couple(fn, _tracer("m", []))

    assert result.__name__ == fn.__name__


def test_couple_runs_middleware_around_the_call():
    log = []
    fn = _make_node()
    result = couple(fn, _tracer("outer", log))

    value = asyncio.run(_run(result, 2, 3))

    assert value == 5
    assert log == ["outer-in", "outer-out"]

    # the original was never touched, so running it directly must not see the
    # newly attached middleware
    log.clear()
    asyncio.run(_run(fn, 2, 3))
    assert log == []


def test_couple_twice_from_same_original_produces_independent_siblings():
    """Two `couple()` calls against the same original RTFunction each branch from
    that original's pristine state -- the second call does not see the first
    call's middleware, and the original itself never accumulates anything."""
    log = []
    fn = _make_node()
    first = couple(fn, _tracer("first", log))
    second = couple(fn, _tracer("second", log))

    asyncio.run(_run(first, 1, 1))
    assert log == ["first-in", "first-out"]

    log.clear()
    asyncio.run(_run(second, 1, 1))
    assert log == ["second-in", "second-out"]

    log.clear()
    asyncio.run(_run(fn, 1, 1))
    assert log == []


def test_couple_chained_composes_first_outer_second_inner():
    """To compose middleware across multiple `couple()` calls, chain off the
    previous result rather than calling `couple()` repeatedly against the same
    original -- each call wraps a fresh layer around whatever it's given."""
    log = []
    fn = _make_node()
    once = couple(fn, _tracer("first", log))
    twice = couple(once, _tracer("second", log))

    asyncio.run(_run(twice, 1, 1))

    # first-coupled is outer, second-coupled is inner
    assert log == ["first-in", "second-in", "second-out", "first-out"]


def test_couple_with_multiple_middleware_in_one_call_preserves_list_order():
    log = []
    fn = _make_node()
    result = couple(fn, _tracer("first", log), _tracer("second", log))

    asyncio.run(_run(result, 1, 1))

    assert log == ["first-in", "second-in", "second-out", "first-out"]


def test_couple_on_class_with_no_prior_middleware():
    fn = _make_node()
    base_cls = fn.node_type
    mw = _tracer("only", [])

    new_cls = couple(base_cls, mw)

    assert new_cls._user_middleware == [mw]


def test_couple_branching_from_same_base_does_not_cross_contaminate():
    """Two independent `couple()` calls against the same base class must not leak
    each other's middleware -- extend_middleware deep-copies the existing
    `_user_middleware` list on every call rather than mutating it in place."""
    fn = _make_node()
    prefix_log = []
    base_with_prefix = couple(fn.node_type, _tracer("prefix", prefix_log))

    log_x, log_y = [], []
    branch_x = base_with_prefix.extend_middleware(_tracer("x", log_x))
    branch_y = base_with_prefix.extend_middleware(_tracer("y", log_y))

    asyncio.run(_run(branch_x, 1, 2))
    assert prefix_log == ["prefix-in", "prefix-out"]
    assert log_x == ["x-in", "x-out"]
    assert log_y == []  # branch_y's middleware never ran

    asyncio.run(_run(branch_y, 3, 4))
    assert log_y == ["y-in", "y-out"]
    assert log_x == ["x-in", "x-out"]  # unchanged by branch_y's run


def test_couple_does_not_affect_a_sibling_built_separately():
    fn_a = _make_node()
    fn_b = _make_node()

    couple(fn_a, _tracer("a", []))

    assert fn_b.node_type._user_middleware == []
