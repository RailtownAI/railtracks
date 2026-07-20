"""Unit tests for `couple` -- post-hoc middleware attachment.
"""

import asyncio

import pytest
import railtracks as rt
from railtracks.interaction import couple
from railtracks.middleware import wrap_node


def _make_node():
    @rt.function_node
    def add(a: int, b: int) -> int:
        return a + b

    return add


def _make_agent(mock_llm, response="hi"):
    return rt.agent_node(
        "TestAgent",
        llm=mock_llm(custom_response=response),
        system_message="you are a helpful assistant",
        context_injection=False,
    )


def _tracer(label, log):
    @wrap_node
    async def m(call, *args, **kwargs):
        log.append(f"{label}-in")
        result = await call(*args, **kwargs)
        log.append(f"{label}-out")
        return result

    return m


def _model_tracer(label, log):
    @rt.wrap_llm
    async def m(call, *args, **kwargs):
        log.append(f"{label}-in")
        result = await call(*args, **kwargs)
        log.append(f"{label}-out")
        return result

    return m


async def _run(node, *args):
    flow = rt.Flow("Test Flow", node)
    return await flow.ainvoke(*args)


async def _run_agent(node_cls, user_input="hello"):
    with rt.Session():
        return await rt.call(node_cls, user_input=user_input)


# =============================== middleware ===============================


def test_couple_on_node_type_returns_new_subclass():
    fn = _make_node()
    original_cls = fn.node_type
    mw = _tracer("m", [])

    new_cls = couple(original_cls, middleware=[mw])

    assert new_cls is not original_cls
    assert issubclass(new_cls, original_cls)
    assert original_cls._user_middleware == []
    assert new_cls._user_middleware == [mw]


def test_couple_on_rt_function_does_not_mutate_node_type_in_place():
    fn = _make_node()
    original_node_type = fn.node_type
    mw = _tracer("m", [])

    result = couple(fn, middleware=[mw])

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
    result = couple(fn, middleware=[_tracer("m", [])])

    assert result.func is fn.func


def test_couple_on_rt_function_preserves_name():
    fn = _make_node()
    result = couple(fn, middleware=[_tracer("m", [])])

    assert result.__name__ == fn.__name__


def test_couple_runs_middleware_around_the_call():
    log = []
    fn = _make_node()
    result = couple(fn, middleware=[_tracer("outer", log)])

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
    first = couple(fn, middleware=[_tracer("first", log)])
    second = couple(fn, middleware=[_tracer("second", log)])

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
    once = couple(fn, middleware=[_tracer("first", log)])
    twice = couple(once, middleware=[_tracer("second", log)])

    asyncio.run(_run(twice, 1, 1))

    # first-coupled is outer, second-coupled is inner
    assert log == ["first-in", "second-in", "second-out", "first-out"]


def test_couple_with_multiple_middleware_in_one_call_preserves_list_order():
    log = []
    fn = _make_node()
    result = couple(
        fn, middleware=[_tracer("first", log), _tracer("second", log)]
    )

    asyncio.run(_run(result, 1, 1))

    assert log == ["first-in", "second-in", "second-out", "first-out"]


def test_couple_on_class_with_no_prior_middleware():
    fn = _make_node()
    base_cls = fn.node_type
    mw = _tracer("only", [])

    new_cls = couple(base_cls, middleware=[mw])

    assert new_cls._user_middleware == [mw]


def test_couple_branching_from_same_base_does_not_cross_contaminate():
    """Two independent `couple()` calls against the same base class must not leak
    each other's middleware -- extend_middleware deep-copies the existing
    `_user_middleware` list on every call rather than mutating it in place."""
    fn = _make_node()
    prefix_log = []
    base_with_prefix = couple(fn.node_type, middleware=[_tracer("prefix", prefix_log)])

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

    couple(fn_a, middleware=[_tracer("a", [])])

    assert fn_b.node_type._user_middleware == []


# ============================= model_middleware =============================


def test_couple_model_middleware_creates_new_subclass_without_mutating_original(
    mock_llm,
):
    agent_cls = _make_agent(mock_llm)
    mw = _model_tracer("m", [])

    new_cls = couple(agent_cls, model_middleware=[mw])

    assert new_cls is not agent_cls
    assert issubclass(new_cls, agent_cls)
    assert agent_cls._user_model_middleware == []
    assert new_cls._user_model_middleware == [mw]


def test_couple_model_middleware_wraps_the_raw_model_call(mock_llm):
    log = []
    agent_cls = _make_agent(mock_llm)

    new_cls = couple(agent_cls, model_middleware=[_model_tracer("m", log)])

    result = asyncio.run(_run_agent(new_cls))

    assert result.content == "hi"
    assert log == ["m-in", "m-out"]

    # original class is untouched, so calling it directly must not see the
    # newly attached model_middleware
    log.clear()
    asyncio.run(_run_agent(agent_cls))
    assert log == []


def test_couple_model_middleware_branching_does_not_cross_contaminate(mock_llm):
    prefix_log = []
    agent_cls = _make_agent(mock_llm)
    base_with_prefix = couple(
        agent_cls, model_middleware=[_model_tracer("prefix", prefix_log)]
    )

    log_x, log_y = [], []
    branch_x = base_with_prefix.extend_model_middleware(_model_tracer("x", log_x))
    branch_y = base_with_prefix.extend_model_middleware(_model_tracer("y", log_y))

    # no leaky pointers: the two branches' lists are distinct objects, and
    # neither is the same list object as their shared base's
    assert branch_x._user_model_middleware is not branch_y._user_model_middleware
    assert (
        branch_x._user_model_middleware
        is not base_with_prefix._user_model_middleware
    )

    asyncio.run(_run_agent(branch_x))
    assert prefix_log == ["prefix-in", "prefix-out"]
    assert log_x == ["x-in", "x-out"]
    assert log_y == []  # branch_y's middleware never ran

    prefix_log.clear()
    asyncio.run(_run_agent(branch_y))
    assert prefix_log == ["prefix-in", "prefix-out"]
    assert log_y == ["y-in", "y-out"]
    assert log_x == ["x-in", "x-out"]  # unchanged by branch_y's run

    # mutating a branch's own list in place must not leak into its sibling or
    # the base it was extended from
    assert len(branch_x._user_model_middleware) == 2  # prefix + x
    branch_x._user_model_middleware.append(_model_tracer("leaky", []))
    assert len(branch_x._user_model_middleware) == 3
    assert len(branch_y._user_model_middleware) == 2  # prefix + y, untouched
    assert len(base_with_prefix._user_model_middleware) == 1  # prefix only, untouched


def test_couple_model_middleware_does_not_affect_a_sibling_built_separately(mock_llm):
    agent_a = _make_agent(mock_llm)
    agent_b = _make_agent(mock_llm)

    couple(agent_a, model_middleware=[_model_tracer("a", [])])

    assert agent_b._user_model_middleware == []


def test_couple_middleware_and_model_middleware_together(mock_llm):
    """You can attach node-level middleware and model-level middleware in the
    same couple() call; each wraps its own boundary and both fire."""
    node_log, model_log = [], []
    agent_cls = _make_agent(mock_llm)

    new_cls = couple(
        agent_cls,
        middleware=[_tracer("node", node_log)],
        model_middleware=[_model_tracer("model", model_log)],
    )

    result = asyncio.run(_run_agent(new_cls))

    assert result.content == "hi"
    assert node_log == ["node-in", "node-out"]
    assert model_log == ["model-in", "model-out"]


def test_couple_model_middleware_alone_leaves_node_middleware_untouched(mock_llm):
    agent_cls = _make_agent(mock_llm)

    new_cls = couple(agent_cls, model_middleware=[_model_tracer("m", [])])

    assert new_cls._user_middleware == agent_cls._user_middleware == []


def test_couple_middleware_alone_leaves_model_middleware_untouched(mock_llm):
    agent_cls = _make_agent(mock_llm)

    new_cls = couple(agent_cls, middleware=[_tracer("m", [])])

    assert new_cls._user_model_middleware == agent_cls._user_model_middleware == []


def test_couple_model_middleware_chained_composes_first_outer_second_inner(mock_llm):
    log = []
    agent_cls = _make_agent(mock_llm)

    once = couple(agent_cls, model_middleware=[_model_tracer("first", log)])
    twice = couple(once, model_middleware=[_model_tracer("second", log)])

    asyncio.run(_run_agent(twice))

    assert log == ["first-in", "second-in", "second-out", "first-out"]


def test_couple_model_middleware_on_rt_function_is_a_documented_no_op():
   
    fn = _make_node()
    with pytest.raises(ValueError):
        result = couple(fn, model_middleware=[_model_tracer("m", [])])


