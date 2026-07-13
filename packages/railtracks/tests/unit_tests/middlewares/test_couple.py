"""Unit tests for `couple` / `Node.extend_middleware` -- post-hoc middleware attachment.

`couple(node, middleware)` takes an iterable of `Middleware` and works on either a
`type[Node]` (returns a new subclass, original untouched) or an `RTFunction` (mutates
`.node_type` in place and returns the same object). Both delegate to
`Node.extend_middleware`, which deep-copies the existing `_user_middleware` list before
appending, so branching from the same base class produces independent subclasses.
"""

import asyncio

import railtracks as rt
from railtracks.interaction import couple
from railtracks.middlewares import wrap_node


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


def test_couple_on_rt_function_mutates_node_type_in_place():
    fn = _make_node()
    mw = _tracer("m", [])

    result = couple(fn, mw)

    assert result is fn
    assert fn.node_type._user_middleware == [mw]


def test_couple_runs_middleware_around_the_call():
    log = []
    fn = _make_node()
    couple(fn, _tracer("outer", log))

    result = asyncio.run(_run(fn, 2, 3))

    assert result == 5
    assert log == ["outer-in", "outer-out"]


def test_couple_twice_composes_build_order_then_coupled_order():
    log = []
    fn = _make_node()
    couple(fn, _tracer("first", log))
    couple(fn, _tracer("second", log))

    asyncio.run(_run(fn, 1, 1))

    # first-coupled is outer, second-coupled is inner (append order == outer-to-inner)
    assert log == ["first-in", "second-in", "second-out", "first-out"]


def test_couple_with_multiple_middleware_in_one_call_preserves_list_order():
    log = []
    fn = _make_node()
    couple(fn, _tracer("first", log), _tracer("second", log))

    asyncio.run(_run(fn, 1, 1))

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
