import asyncio

import pytest
import pytest_asyncio
from unittest.mock import MagicMock, patch

from railtracks.prebuilt.tools.todo.todos import State, ToDo, ToDoToolSet


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def ts():
    return ToDoToolSet()


@pytest.fixture
def ts_with_callback():
    cb = MagicMock()
    return ToDoToolSet(callback=cb), cb


@pytest_asyncio.fixture
async def populated(ts):
    await ts.add("task-a", "Description of task A")
    await ts.add("task-b", "Description of task B", state=State.IN_PROGRESS)
    await ts.add("task-c", "Description of task C", state=State.COMPLETED)
    return ts


@pytest_asyncio.fixture
async def full_populated(ts):
    await ts.add("task-a", "Description of task A")
    await ts.add("task-b", "Description of task B", state=State.IN_PROGRESS)
    await ts.add("task-c", "Description of task C", state=State.COMPLETED)
    await ts.add("task-d", "Description of task D", state=State.FAILED)
    await ts.add("task-e", "Description of task E", state=State.NO_LONGER_PLANNED)
    return ts


# ---------------------------------------------------------------------------
# Initialisation
# ---------------------------------------------------------------------------

def test_init_empty_todos(ts):
    assert ts.todos == []


async def test_init_custom_callback():
    cb = MagicMock()
    t = ToDoToolSet(callback=cb)
    await t.add("x", "desc x")
    cb.assert_called_once_with("x", "desc x", State.NOT_STARTED)


# ---------------------------------------------------------------------------
# add()
# ---------------------------------------------------------------------------

async def test_add_appends_todo(ts):
    await ts.add("buy milk", "Pick up 2 litres of whole milk")
    assert len(ts.todos) == 1
    assert ts.todos[0].short_description == "buy milk"


async def test_add_default_state_is_not_started(ts):
    await ts.add("task", "some description")
    assert ts.todos[0].state == State.NOT_STARTED


async def test_add_explicit_state(ts):
    await ts.add("task", "some description", state=State.IN_PROGRESS)
    assert ts.todos[0].state == State.IN_PROGRESS


async def test_add_duplicate_short_description_raises(ts):
    await ts.add("task", "first description")
    with pytest.raises(ValueError, match="short description"):
        await ts.add("task", "different description")


async def test_add_duplicate_description_raises(ts):
    await ts.add("task one", "shared description")
    with pytest.raises(ValueError, match="description"):
        await ts.add("task two", "shared description")


async def test_add_callback_fires_after_validation(ts_with_callback):
    ts, cb = ts_with_callback
    await ts.add("task", "valid description")
    cb.assert_called_once()


async def test_add_callback_not_fired_on_validation_failure(ts_with_callback):
    ts, cb = ts_with_callback
    await ts.add("task", "description")
    cb.reset_mock()
    with pytest.raises(ValueError):
        await ts.add("task", "different description")
    cb.assert_not_called()


async def test_add_callback_exception_is_logged_and_todo_still_added(ts):
    failing_cb = MagicMock(side_effect=RuntimeError("boom"))
    t = ToDoToolSet(callback=failing_cb)
    with patch("railtracks.prebuilt.tools.todo.todos.logger") as mock_logger:
        await t.add("task", "description")
        mock_logger.error.assert_called_once()
    assert len(t.todos) == 1


# ---------------------------------------------------------------------------
# ID assignment
# ---------------------------------------------------------------------------

async def test_first_todo_gets_id_1(ts):
    await ts.add("task", "description")
    assert ts.todos[0].id == 1


async def test_ids_are_sequential(ts):
    await ts.add("task-a", "desc a")
    await ts.add("task-b", "desc b")
    await ts.add("task-c", "desc c")
    assert [t.id for t in ts.todos] == [1, 2, 3]


async def test_ids_are_unique_within_instance(ts):
    for i in range(10):
        await ts.add(f"task-{i}", f"desc {i}")
    ids = [t.id for t in ts.todos]
    assert len(ids) == len(set(ids))


async def test_id_counters_are_independent_per_instance():
    t1 = ToDoToolSet()
    t2 = ToDoToolSet()
    await t1.add("task-a", "desc a")
    await t1.add("task-b", "desc b")
    await t2.add("task-x", "desc x")
    assert t1.todos[0].id == 1
    assert t1.todos[1].id == 2
    assert t2.todos[0].id == 1


async def test_id_included_in_complete_print(ts):
    await ts.add("task", "description")
    assert "(1)" in ts.todos[0].complete_print()


async def test_failed_add_does_not_increment_id_counter(ts):
    await ts.add("task-a", "desc a")
    with pytest.raises(ValueError):
        await ts.add("task-a", "different desc")  # duplicate short_description
    await ts.add("task-b", "desc b")
    assert ts.todos[1].id == 2  # gap-free: failure must not consume an id


# ---------------------------------------------------------------------------
# get_all_todos()
# ---------------------------------------------------------------------------

async def test_get_all_todos_empty(ts):
    assert await ts.get_all_todos() == []


async def test_get_all_todos_returns_formatted_strings(populated):
    result = await populated.get_all_todos()
    assert len(result) == 3
    assert all(isinstance(s, str) for s in result)


async def test_get_all_todos_excludes_no_longer_planned(full_populated):
    result = await full_populated.get_all_todos()
    descriptions = " ".join(result)
    assert "task-e" not in descriptions
    assert len(result) == 4


# ---------------------------------------------------------------------------
# get_completed_todos() / get_not_started_todos() / get_incomplete_todos()
# ---------------------------------------------------------------------------

async def test_get_completed_todos(populated):
    result = await populated.get_completed_todos()
    assert len(result) == 1
    assert "task-c" in result[0]


async def test_get_not_started_todos(populated):
    result = await populated.get_not_started_todos()
    assert len(result) == 1
    assert "task-a" in result[0]


async def test_get_incomplete_todos_includes_not_started_and_in_progress(populated):
    result = await populated.get_incomplete_todos()
    assert len(result) == 2
    descriptions = " ".join(result)
    assert "task-a" in descriptions
    assert "task-b" in descriptions
    assert "task-c" not in descriptions


async def test_get_incomplete_todos_includes_failed(full_populated):
    result = await full_populated.get_incomplete_todos()
    descriptions = " ".join(result)
    assert "task-d" in descriptions


async def test_get_incomplete_todos_excludes_no_longer_planned(full_populated):
    result = await full_populated.get_incomplete_todos()
    descriptions = " ".join(result)
    assert "task-e" not in descriptions


# ---------------------------------------------------------------------------
# get_failed_todos()
# ---------------------------------------------------------------------------

async def test_get_failed_todos_empty(populated):
    assert await populated.get_failed_todos() == []


async def test_get_failed_todos_returns_only_failed(full_populated):
    result = await full_populated.get_failed_todos()
    assert len(result) == 1
    assert "task-d" in result[0]


# ---------------------------------------------------------------------------
# complete_todo_by_id() / start_todo_by_id() / update_todo_by_id()
# ---------------------------------------------------------------------------

async def test_complete_todo_by_id(ts):
    await ts.add("task", "description")
    todo_id = ts.todos[0].id
    result = await ts.complete_todo_by_id(todo_id)
    assert ts.todos[0].state == State.COMPLETED
    assert "Successfully completed" in result


async def test_complete_todo_by_id_not_found(ts):
    with pytest.raises(ValueError, match="not found"):
        await ts.complete_todo_by_id(999)


async def test_start_todo_by_id(ts):
    await ts.add("task", "description")
    todo_id = ts.todos[0].id
    result = await ts.start_todo_by_id(todo_id)
    assert ts.todos[0].state == State.IN_PROGRESS
    assert "Successfully started" in result


async def test_start_todo_by_id_not_found(ts):
    with pytest.raises(ValueError, match="not found"):
        await ts.start_todo_by_id(999)


async def test_update_todo_by_id(ts):
    await ts.add("task", "description")
    todo_id = ts.todos[0].id
    result = await ts.update_todo_by_id(todo_id, State.COMPLETED)
    assert ts.todos[0].state == State.COMPLETED
    assert "Successfully updated" in result


async def test_update_todo_by_id_not_found(ts):
    with pytest.raises(ValueError, match="not found"):
        await ts.update_todo_by_id(999, State.COMPLETED)


# ---------------------------------------------------------------------------
# fail_todo_by_id()
# ---------------------------------------------------------------------------

async def test_fail_todo_by_id(ts):
    await ts.add("task", "description")
    todo_id = ts.todos[0].id
    result = await ts.fail_todo_by_id(todo_id)
    assert ts.todos[0].state == State.FAILED
    assert "failed" in result


async def test_fail_todo_by_id_not_found(ts):
    with pytest.raises(ValueError, match="not found"):
        await ts.fail_todo_by_id(999)


# ---------------------------------------------------------------------------
# no_longer_plan_todo_by_id()
# ---------------------------------------------------------------------------

async def test_no_longer_plan_todo_by_id(ts):
    await ts.add("task", "description")
    todo_id = ts.todos[0].id
    result = await ts.no_longer_plan_todo_by_id(todo_id)
    assert ts.todos[0].state == State.NO_LONGER_PLANNED
    assert "no longer planned" in result


async def test_no_longer_plan_todo_by_id_not_found(ts):
    with pytest.raises(ValueError, match="not found"):
        await ts.no_longer_plan_todo_by_id(999)


# ---------------------------------------------------------------------------
# make_all_no_longer_planned()
# ---------------------------------------------------------------------------

async def test_make_all_no_longer_planned_affects_not_started_and_in_progress(ts):
    await ts.add("task-a", "desc a")
    await ts.add("task-b", "desc b", state=State.IN_PROGRESS)
    await ts.add("task-c", "desc c", state=State.COMPLETED)
    await ts.add("task-d", "desc d", state=State.FAILED)
    await ts.make_all_no_longer_planned()
    assert ts.todos[0].state == State.NO_LONGER_PLANNED
    assert ts.todos[1].state == State.NO_LONGER_PLANNED
    assert ts.todos[2].state == State.COMPLETED
    assert ts.todos[3].state == State.FAILED


async def test_make_all_no_longer_planned_returns_count(ts):
    await ts.add("task-a", "desc a")
    await ts.add("task-b", "desc b", state=State.IN_PROGRESS)
    await ts.add("task-c", "desc c", state=State.COMPLETED)
    result = await ts.make_all_no_longer_planned()
    assert "2" in result


async def test_make_all_no_longer_planned_empty(ts):
    result = await ts.make_all_no_longer_planned()
    assert "0" in result


# ---------------------------------------------------------------------------
# pretty_dashboard()
# ---------------------------------------------------------------------------

async def test_pretty_dashboard_empty(ts):
    assert await ts.pretty_dashboard() == "No todos found."


async def test_pretty_dashboard_lists_todos(populated):
    result = await populated.pretty_dashboard()
    assert "task-a" in result
    assert "task-b" in result
    assert "task-c" in result


async def test_pretty_dashboard_excludes_no_longer_planned(full_populated):
    result = await full_populated.pretty_dashboard()
    assert "task-e" not in result


async def test_pretty_dashboard_only_no_longer_planned_shows_empty(ts):
    await ts.add("task", "description", state=State.NO_LONGER_PLANNED)
    assert await ts.pretty_dashboard() == "No todos found."


# ---------------------------------------------------------------------------
# Instance isolation
# ---------------------------------------------------------------------------

async def test_two_instances_are_isolated():
    t1 = ToDoToolSet()
    t2 = ToDoToolSet()
    await t1.add("task", "description")
    assert len(t1.todos) == 1
    assert len(t2.todos) == 0


# ---------------------------------------------------------------------------
# tool_set()
# ---------------------------------------------------------------------------

def test_tool_set_returns_rt_functions(ts):
    tools = ts.tool_set()
    assert len(tools) > 0
    assert all(hasattr(t, "node_type") for t in tools)


async def test_tool_set_bound_to_instance():
    t1 = ToDoToolSet()
    t2 = ToDoToolSet()
    add_tool = t1.tool_set()[0]
    await add_tool("task", "description")
    assert len(t1.todos) == 1
    assert len(t2.todos) == 0


# ---------------------------------------------------------------------------
# prompt()
# ---------------------------------------------------------------------------

def test_prompt_is_non_empty_string():
    result = ToDoToolSet.prompt()
    assert isinstance(result, str)
    assert len(result) > 0


# ---------------------------------------------------------------------------
# Concurrency
# ---------------------------------------------------------------------------

async def test_concurrent_adds_produce_unique_sequential_ids():
    ts = ToDoToolSet()
    n = 50
    errors = []

    async def add_todo(i):
        try:
            await ts.add(f"task-{i}", f"desc {i}")
        except Exception as e:
            errors.append(e)

    await asyncio.gather(*[add_todo(i) for i in range(n)])

    assert not errors
    assert len(ts.todos) == n
    ids = [todo.id for todo in ts.todos]
    assert len(set(ids)) == n               # no duplicates
    assert set(ids) == set(range(1, n + 1)) # exactly 1..n, no gaps


async def test_concurrent_adds_no_lost_updates():
    ts = ToDoToolSet()
    n = 100

    await asyncio.gather(*[ts.add(f"task-{i}", f"desc {i}") for i in range(n)])

    assert len(ts.todos) == n


async def test_concurrent_reads_during_writes_do_not_raise():
    ts = ToDoToolSet()
    errors = []

    async def writer():
        for i in range(50):
            await ts.add(f"task-{i}", f"desc {i}")

    async def reader():
        for _ in range(100):
            try:
                await ts.get_all_todos()
            except Exception as e:
                errors.append(e)

    await asyncio.gather(writer(), *[reader() for _ in range(5)])

    assert not errors


async def test_concurrent_state_transitions_on_distinct_todos():
    ts = ToDoToolSet()
    n = 20
    for i in range(n):
        await ts.add(f"task-{i}", f"desc {i}")

    ids = [todo.id for todo in ts.todos]
    errors = []

    async def complete(todo_id):
        try:
            await ts.complete_todo_by_id(todo_id)
        except Exception as e:
            errors.append(e)

    await asyncio.gather(*[complete(tid) for tid in ids])

    assert not errors
    assert all(todo.state == State.COMPLETED for todo in ts.todos)


async def test_callback_fires_after_todo_is_committed():
    seen_lengths = []
    ts = ToDoToolSet()

    def callback(short_desc, desc, state):
        # todo must already be in the list when callback fires
        seen_lengths.append(len(ts.todos))

    ts = ToDoToolSet(callback=callback)
    await ts.add("task", "description")

    assert len(ts.todos) == 1
    assert seen_lengths == [1]
