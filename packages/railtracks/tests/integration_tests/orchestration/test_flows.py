import asyncio
import sqlite3
import threading

import pytest
import railtracks as rt
from railtracks.orchestration.flow import Flow


@rt.function_node
async def echo(value: str) -> str:
    return value


@rt.function_node
async def add(a: int, b: int) -> int:
    return a + b


@rt.function_node
def sync_upper(text: str) -> str:
    return text.upper()


@rt.function_node
async def boom(text: str) -> str:
    raise ValueError("database connection pool exhausted")


@rt.function_node
def read_context_value(key: str, default: str | None = None):
    return rt.context.get(key, default=default)


@rt.function_node
def context_snapshot():
    return {k: rt.context.get(k) for k in rt.context.keys()}


@rt.function_node
async def grandchild_snapshot():
    return {k: rt.context.get(k) for k in rt.context.keys()}


@rt.function_node
async def child_put(key: str, value: str):
    rt.context.put(key, value)
    return await rt.call(grandchild_snapshot)


@rt.function_node
async def child_delete(key: str):
    rt.context.delete(key)
    return await rt.call(grandchild_snapshot)


@rt.function_node
async def root_tree_flow():
    rt.context.put("root", "r1")
    before_child = await rt.call(grandchild_snapshot)
    after_child = await rt.call(child_put, "child", "c1")
    rt.context.put("root", "r2")
    after_update = await rt.call(grandchild_snapshot)
    return before_child, after_child, after_update


@rt.function_node
async def root_delete_flow():
    rt.context.put("root", "r1")
    rt.context.put("temp", "t1")
    after_delete = await rt.call(child_delete, "temp")
    return after_delete


def test_flow_invoke_sync_returns_value():
    flow = Flow(name="echo-flow", entry_point=echo)
    result = flow.invoke("hello")
    assert result == "hello"


def test_flow_invoke_sync_function_entry_point():
    flow = Flow(name="sync-upper-flow", entry_point=sync_upper)
    result = flow.invoke("hello")
    assert result == "HELLO"


@pytest.mark.asyncio
async def test_flow_ainvoke_async_returns_value():
    flow = Flow(name="add-flow", entry_point=add)
    result = await flow.ainvoke(1, 2)
    assert result == 3


def test_flow_invoke_surfaces_internal_runtime_error():
    flow = Flow(name="boom-flow", entry_point=boom, save_state=False)

    with pytest.raises(ValueError, match="database connection pool exhausted"):
        flow.invoke("x")


@pytest.mark.asyncio
async def test_flow_ainvoke_surfaces_internal_runtime_error():
    flow = Flow(name="boom-flow", entry_point=boom, save_state=False)

    with pytest.raises(ValueError, match="database connection pool exhausted"):
        await flow.ainvoke("x")


@pytest.mark.asyncio
async def test_flow_invoke_in_an_event_loop():
    # invoke() must work transparently even when called from inside a running
    # event loop (e.g. Jupyter) — it should dispatch to a worker thread rather
    # than raising RuntimeError.
    flow = Flow(name="add-flow", entry_point=add)
    result = flow.invoke(1, 2)
    assert result == 3


@pytest.mark.asyncio
async def test_flow_invoke_in_event_loop_preserves_context():
    # Context set on the Flow must be visible inside the worker-thread run.
    flow = Flow(
        name="context-invoke-loop-flow",
        entry_point=read_context_value,
        context={"env": "notebook"},
    )
    result = flow.invoke("env")
    assert result == "notebook"


def test_flow_context_is_passed_to_node():
    flow = Flow(
        name="context-flow",
        entry_point=read_context_value,
        context={"user_id": "abc123"},
    )
    result = flow.invoke("user_id")
    assert result == "abc123"


def test_flow_update_context_merges_and_preserves_original():
    base_flow = Flow(
        name="snapshot-flow",
        entry_point=context_snapshot,
        context={"a": 1, "b": 2},
    )

    updated_flow = base_flow.update_context({"b": 3, "c": 4})

    base_result = base_flow.invoke()
    updated_result = updated_flow.invoke()

    assert base_result == {"a": 1, "b": 2}
    assert updated_result == {"a": 1, "b": 3, "c": 4}


def test_flow_ainvoke_in_new_event_loop():
    flow = Flow(name="echo-flow", entry_point=echo)

    async def run():
        return await flow.ainvoke("looped")

    result = asyncio.run(run())
    assert result == "looped"


def test_flow_context_tree_propagation_across_nested_calls():
    flow = Flow(
        name="tree-context-flow",
        entry_point=root_tree_flow,
        context={"seed": "s"},
    )

    before_child, after_child, after_update = flow.invoke()

    assert before_child == {"seed": "s", "root": "r1"}
    assert after_child == {"seed": "s", "root": "r1", "child": "c1"}
    assert after_update == {"seed": "s", "root": "r2", "child": "c1"}


def test_flow_context_tree_delete_propagates_within_run():
    flow = Flow(
        name="tree-delete-flow",
        entry_point=root_delete_flow,
        context={"seed": "s"},
    )

    after_delete = flow.invoke()

    assert after_delete == {"seed": "s", "root": "r1"}


def test_flow_context_mutations_do_not_leak_between_runs():
    @rt.function_node
    async def mutate_context():
        rt.context.put("transient", "value")
        return await rt.call(grandchild_snapshot)

    mutate_flow = Flow(
        name="mutate-context-flow",
        entry_point=mutate_context,
        context={"seed": "s"},
    )
    read_flow = Flow(
        name="read-context-flow",
        entry_point=grandchild_snapshot,
        context={"seed": "s"},
    )

    mutated_snapshot = mutate_flow.invoke()
    clean_snapshot = read_flow.invoke()

    assert mutated_snapshot == {"seed": "s", "transient": "value"}
    assert clean_snapshot == {"seed": "s"}


def test_flow_equality_hash_same_name_is_stable():
    flow = Flow(name="stable-flow", entry_point=echo)

    first_hash = flow.equality_hash()
    second_hash = flow.equality_hash()

    assert first_hash == second_hash


def test_flow_equality_hash_ignores_other_config():
    base_flow = Flow(
        name="same-name",
        entry_point=echo,
        context={"a": 1},
        timeout=10,
    )
    different_flow = Flow(
        name="same-name",
        entry_point=add,
        context={"b": 2},
        timeout=20,
        end_on_error=True,
    )

    assert base_flow.equality_hash() == different_flow.equality_hash()


def test_flow_equality_hash_changes_with_name():
    first = Flow(name="flow-a", entry_point=echo)
    second = Flow(name="flow-b", entry_point=echo)

    assert first.equality_hash() != second.equality_hash()


# ---------------------------------------------------------------------------
# Regression: context values are shared, not deep-copied (issue #1675)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "make_resource",
    [threading.Lock, lambda: sqlite3.connect(":memory:")],
    ids=["threading.Lock", "sqlite3.Connection"],
)
def test_flow_invoke_passes_non_copyable_context_value_by_reference(make_resource):
    resource = make_resource()

    @rt.function_node
    def holds_caller_object() -> bool:
        return rt.context.get("resource") is resource

    flow = Flow(
        name="resource-flow",
        entry_point=holds_caller_object,
        context={"resource": resource},
    )
    assert flow.invoke() is True
    assert flow.invoke() is True

    if isinstance(resource, sqlite3.Connection):
        resource.close()


def test_flow_context_values_are_shared_across_runs():
    """A run's writes into a nested value reach the caller's object and the next run."""
    cache: dict[str, int] = {}

    @rt.function_node
    def count_hit() -> int:
        hits = rt.context.get("cache")
        hits["n"] = hits.get("n", 0) + 1
        return hits["n"]

    flow = Flow(
        name="shared-cache-flow", entry_point=count_hit, context={"cache": cache}
    )
    assert flow.invoke() == 1
    assert flow.invoke() == 2
    assert cache == {"n": 2}


def test_flow_context_put_and_delete_stay_in_their_run():
    @rt.function_node
    async def put_delete_snapshot():
        before = {k: rt.context.get(k) for k in rt.context.keys()}
        rt.context.put("transient", "value")
        rt.context.delete("seed")
        return before

    flow = Flow(
        name="put-delete-flow",
        entry_point=put_delete_snapshot,
        context={"seed": "s"},
    )
    assert flow.invoke() == {"seed": "s"}
    assert flow.invoke() == {"seed": "s"}
    assert flow._context == {"seed": "s"}


def test_flow_concurrent_runs_keep_their_own_top_level_keys():
    @rt.function_node
    async def put_then_read(value: str) -> str:
        rt.context.put("owner", value)
        await asyncio.sleep(0.01)
        return rt.context.get("owner")

    flow = Flow(
        name="concurrent-put-flow",
        entry_point=put_then_read,
        context={"owner": "flow"},
    )

    async def run_both() -> list[str]:
        return await asyncio.gather(flow.ainvoke("a"), flow.ainvoke("b"))

    assert asyncio.run(run_both()) == ["a", "b"]
    assert flow._context == {"owner": "flow"}


def test_flow_update_context_keeps_non_copyable_values_by_reference():
    lock = threading.Lock()
    flow = Flow(
        name="lock-update-flow",
        entry_point=context_snapshot,
        context={"lock": lock, "a": 1},
    )

    updated = flow.update_context({"a": 2, "b": 3})

    assert updated.invoke() == {"lock": lock, "a": 2, "b": 3}
    assert flow.invoke() == {"lock": lock, "a": 1}


def test_flow_update_context_returns_an_independent_flow():
    extra = {"a": 99, "b": 2}
    flow = Flow(name="orig-flow", entry_point=echo, context={"a": 1})

    updated = flow.update_context(extra)
    extra["b"] = 3

    assert flow._context == {"a": 1}
    assert updated._context == {"a": 99, "b": 2}
    assert updated._context is not flow._context
    assert updated.entry_point is flow.entry_point
    assert updated.name == flow.name


def test_flow_update_context_on_a_flow_without_context():
    flow = Flow(name="empty-context-flow", entry_point=context_snapshot)

    updated = flow.update_context({"a": 1})

    assert updated.invoke() == {"a": 1}
    assert flow.invoke() == {}
