import threading

import pytest
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


@pytest.fixture
def populated(ts):
    ts.add("task-a", "Description of task A")
    ts.add("task-b", "Description of task B", state=State.IN_PROGRESS)
    ts.add("task-c", "Description of task C", state=State.COMPLETED)
    return ts


@pytest.fixture
def full_populated(ts):
    ts.add("task-a", "Description of task A")
    ts.add("task-b", "Description of task B", state=State.IN_PROGRESS)
    ts.add("task-c", "Description of task C", state=State.COMPLETED)
    ts.add("task-d", "Description of task D", state=State.FAILED)
    ts.add("task-e", "Description of task E", state=State.NO_LONGER_PLANNED)
    return ts


# ---------------------------------------------------------------------------
# Initialisation
# ---------------------------------------------------------------------------

def test_init_empty_todos(ts):
    assert ts.todos == []


def test_init_custom_callback():
    cb = MagicMock()
    t = ToDoToolSet(callback=cb)
    t.add("x", "desc x")
    cb.assert_called_once_with("x", "desc x", State.NOT_STARTED)


# ---------------------------------------------------------------------------
# add()
# ---------------------------------------------------------------------------

def test_add_appends_todo(ts):
    ts.add("buy milk", "Pick up 2 litres of whole milk")
    assert len(ts.todos) == 1
    assert ts.todos[0].short_description == "buy milk"


def test_add_default_state_is_not_started(ts):
    ts.add("task", "some description")
    assert ts.todos[0].state == State.NOT_STARTED


def test_add_explicit_state(ts):
    ts.add("task", "some description", state=State.IN_PROGRESS)
    assert ts.todos[0].state == State.IN_PROGRESS


def test_add_duplicate_short_description_raises(ts):
    ts.add("task", "first description")
    with pytest.raises(ValueError, match="short description"):
        ts.add("task", "different description")


def test_add_duplicate_description_raises(ts):
    ts.add("task one", "shared description")
    with pytest.raises(ValueError, match="description"):
        ts.add("task two", "shared description")


def test_add_callback_fires_after_validation(ts_with_callback):
    ts, cb = ts_with_callback
    ts.add("task", "valid description")
    cb.assert_called_once()


def test_add_callback_not_fired_on_validation_failure(ts_with_callback):
    ts, cb = ts_with_callback
    ts.add("task", "description")
    cb.reset_mock()
    with pytest.raises(ValueError):
        ts.add("task", "different description")
    cb.assert_not_called()


def test_add_callback_exception_is_logged_and_todo_still_added(ts):
    failing_cb = MagicMock(side_effect=RuntimeError("boom"))
    t = ToDoToolSet(callback=failing_cb)
    with patch("railtracks.prebuilt.tools.todo.todos.logger") as mock_logger:
        t.add("task", "description")
        mock_logger.error.assert_called_once()
    assert len(t.todos) == 1


# ---------------------------------------------------------------------------
# ID assignment
# ---------------------------------------------------------------------------

def test_first_todo_gets_id_1(ts):
    ts.add("task", "description")
    assert ts.todos[0].id == 1


def test_ids_are_sequential(ts):
    ts.add("task-a", "desc a")
    ts.add("task-b", "desc b")
    ts.add("task-c", "desc c")
    assert [t.id for t in ts.todos] == [1, 2, 3]


def test_ids_are_unique_within_instance(ts):
    for i in range(10):
        ts.add(f"task-{i}", f"desc {i}")
    ids = [t.id for t in ts.todos]
    assert len(ids) == len(set(ids))


def test_id_counters_are_independent_per_instance():
    t1 = ToDoToolSet()
    t2 = ToDoToolSet()
    t1.add("task-a", "desc a")
    t1.add("task-b", "desc b")
    t2.add("task-x", "desc x")
    assert t1.todos[0].id == 1
    assert t1.todos[1].id == 2
    assert t2.todos[0].id == 1


def test_id_included_in_complete_print(ts):
    ts.add("task", "description")
    assert "(1)" in ts.todos[0].complete_print()


def test_failed_add_does_not_increment_id_counter(ts):
    ts.add("task-a", "desc a")
    with pytest.raises(ValueError):
        ts.add("task-a", "different desc")  # duplicate short_description
    ts.add("task-b", "desc b")
    assert ts.todos[1].id == 2  # gap-free: failure must not consume an id


# ---------------------------------------------------------------------------
# get_all_todos()
# ---------------------------------------------------------------------------

def test_get_all_todos_empty(ts):
    assert ts.get_all_todos() == []


def test_get_all_todos_returns_formatted_strings(populated):
    result = populated.get_all_todos()
    assert len(result) == 3
    assert all(isinstance(s, str) for s in result)


def test_get_all_todos_excludes_no_longer_planned(full_populated):
    result = full_populated.get_all_todos()
    descriptions = " ".join(result)
    assert "task-e" not in descriptions
    assert len(result) == 4


# ---------------------------------------------------------------------------
# get_completed_todos() / get_not_started_todos() / get_incomplete_todos()
# ---------------------------------------------------------------------------

def test_get_completed_todos(populated):
    result = populated.get_completed_todos()
    assert len(result) == 1
    assert "task-c" in result[0]


def test_get_not_started_todos(populated):
    result = populated.get_not_started_todos()
    assert len(result) == 1
    assert "task-a" in result[0]


def test_get_incomplete_todos_includes_not_started_and_in_progress(populated):
    result = populated.get_incomplete_todos()
    assert len(result) == 2
    descriptions = " ".join(result)
    assert "task-a" in descriptions
    assert "task-b" in descriptions
    assert "task-c" not in descriptions


def test_get_incomplete_todos_includes_failed(full_populated):
    result = full_populated.get_incomplete_todos()
    descriptions = " ".join(result)
    assert "task-d" in descriptions


def test_get_incomplete_todos_excludes_no_longer_planned(full_populated):
    result = full_populated.get_incomplete_todos()
    descriptions = " ".join(result)
    assert "task-e" not in descriptions


# ---------------------------------------------------------------------------
# get_failed_todos()
# ---------------------------------------------------------------------------

def test_get_failed_todos_empty(populated):
    assert populated.get_failed_todos() == []


def test_get_failed_todos_returns_only_failed(full_populated):
    result = full_populated.get_failed_todos()
    assert len(result) == 1
    assert "task-d" in result[0]


# ---------------------------------------------------------------------------
# complete_todo_by_id() / start_todo_by_id() / update_todo_by_id()
# ---------------------------------------------------------------------------

def test_complete_todo_by_id(ts):
    ts.add("task", "description")
    todo_id = ts.todos[0].id
    result = ts.complete_todo_by_id(todo_id)
    assert ts.todos[0].state == State.COMPLETED
    assert "Successfully completed" in result


def test_complete_todo_by_id_not_found(ts):
    with pytest.raises(ValueError, match="not found"):
        ts.complete_todo_by_id(999)


def test_start_todo_by_id(ts):
    ts.add("task", "description")
    todo_id = ts.todos[0].id
    result = ts.start_todo_by_id(todo_id)
    assert ts.todos[0].state == State.IN_PROGRESS
    assert "Successfully started" in result


def test_start_todo_by_id_not_found(ts):
    with pytest.raises(ValueError, match="not found"):
        ts.start_todo_by_id(999)


def test_update_todo_by_id(ts):
    ts.add("task", "description")
    todo_id = ts.todos[0].id
    result = ts.update_todo_by_id(todo_id, State.COMPLETED)
    assert ts.todos[0].state == State.COMPLETED
    assert "Successfully updated" in result


def test_update_todo_by_id_not_found(ts):
    with pytest.raises(ValueError, match="not found"):
        ts.update_todo_by_id(999, State.COMPLETED)


# ---------------------------------------------------------------------------
# fail_todo_by_id()
# ---------------------------------------------------------------------------

def test_fail_todo_by_id(ts):
    ts.add("task", "description")
    todo_id = ts.todos[0].id
    result = ts.fail_todo_by_id(todo_id)
    assert ts.todos[0].state == State.FAILED
    assert "failed" in result


def test_fail_todo_by_id_not_found(ts):
    with pytest.raises(ValueError, match="not found"):
        ts.fail_todo_by_id(999)


# ---------------------------------------------------------------------------
# no_longer_plan_todo_by_id()
# ---------------------------------------------------------------------------

def test_no_longer_plan_todo_by_id(ts):
    ts.add("task", "description")
    todo_id = ts.todos[0].id
    result = ts.no_longer_plan_todo_by_id(todo_id)
    assert ts.todos[0].state == State.NO_LONGER_PLANNED
    assert "no longer planned" in result


def test_no_longer_plan_todo_by_id_not_found(ts):
    with pytest.raises(ValueError, match="not found"):
        ts.no_longer_plan_todo_by_id(999)


# ---------------------------------------------------------------------------
# make_all_no_longer_planned()
# ---------------------------------------------------------------------------

def test_make_all_no_longer_planned_affects_not_started_and_in_progress(ts):
    ts.add("task-a", "desc a")
    ts.add("task-b", "desc b", state=State.IN_PROGRESS)
    ts.add("task-c", "desc c", state=State.COMPLETED)
    ts.add("task-d", "desc d", state=State.FAILED)
    ts.make_all_no_longer_planned()
    assert ts.todos[0].state == State.NO_LONGER_PLANNED
    assert ts.todos[1].state == State.NO_LONGER_PLANNED
    assert ts.todos[2].state == State.COMPLETED
    assert ts.todos[3].state == State.FAILED


def test_make_all_no_longer_planned_returns_count(ts):
    ts.add("task-a", "desc a")
    ts.add("task-b", "desc b", state=State.IN_PROGRESS)
    ts.add("task-c", "desc c", state=State.COMPLETED)
    result = ts.make_all_no_longer_planned()
    assert "2" in result


def test_make_all_no_longer_planned_empty(ts):
    result = ts.make_all_no_longer_planned()
    assert "0" in result


# ---------------------------------------------------------------------------
# pretty_dashboard()
# ---------------------------------------------------------------------------

def test_pretty_dashboard_empty(ts):
    assert ts.pretty_dashboard() == "No todos found."


def test_pretty_dashboard_lists_todos(populated):
    result = populated.pretty_dashboard()
    assert "task-a" in result
    assert "task-b" in result
    assert "task-c" in result


def test_pretty_dashboard_excludes_no_longer_planned(full_populated):
    result = full_populated.pretty_dashboard()
    assert "task-e" not in result


def test_pretty_dashboard_only_no_longer_planned_shows_empty(ts):
    ts.add("task", "description", state=State.NO_LONGER_PLANNED)
    assert ts.pretty_dashboard() == "No todos found."


# ---------------------------------------------------------------------------
# Instance isolation
# ---------------------------------------------------------------------------

def test_two_instances_are_isolated():
    t1 = ToDoToolSet()
    t2 = ToDoToolSet()
    t1.add("task", "description")
    assert len(t1.todos) == 1
    assert len(t2.todos) == 0


# ---------------------------------------------------------------------------
# tool_set()
# ---------------------------------------------------------------------------

def test_tool_set_returns_rt_functions(ts):
    tools = ts.tool_set()
    assert len(tools) > 0
    assert all(hasattr(t, "node_type") for t in tools)


def test_tool_set_bound_to_instance():
    t1 = ToDoToolSet()
    t2 = ToDoToolSet()
    add_tool = t1.tool_set()[0]
    add_tool("task", "description")
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
# Thread safety
# ---------------------------------------------------------------------------

def test_concurrent_adds_produce_unique_sequential_ids():
    ts = ToDoToolSet()
    n = 50
    errors = []

    def add_todo(i):
        try:
            ts.add(f"task-{i}", f"desc {i}")
        except Exception as e:
            errors.append(e)

    threads = [threading.Thread(target=add_todo, args=(i,)) for i in range(n)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert not errors
    assert len(ts.todos) == n
    ids = [todo.id for todo in ts.todos]
    assert len(set(ids)) == n               # no duplicates
    assert set(ids) == set(range(1, n + 1)) # exactly 1..n, no gaps


def test_concurrent_adds_no_lost_updates():
    ts = ToDoToolSet()
    n = 100

    threads = [
        threading.Thread(target=ts.add, args=(f"task-{i}", f"desc {i}"))
        for i in range(n)
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(ts.todos) == n


def test_concurrent_reads_during_writes_do_not_raise():
    ts = ToDoToolSet()
    stop = threading.Event()
    errors = []

    def writer():
        for i in range(50):
            ts.add(f"task-{i}", f"desc {i}")

    def reader():
        while not stop.is_set():
            try:
                ts.get_all_todos()
            except Exception as e:
                errors.append(e)

    reader_threads = [threading.Thread(target=reader) for _ in range(5)]
    writer_thread = threading.Thread(target=writer)

    for t in reader_threads:
        t.start()
    writer_thread.start()
    writer_thread.join()
    stop.set()
    for t in reader_threads:
        t.join()

    assert not errors


def test_concurrent_state_transitions_on_distinct_todos():
    ts = ToDoToolSet()
    n = 20
    for i in range(n):
        ts.add(f"task-{i}", f"desc {i}")

    ids = [todo.id for todo in ts.todos]
    errors = []

    def complete(todo_id):
        try:
            ts.complete_todo_by_id(todo_id)
        except Exception as e:
            errors.append(e)

    threads = [threading.Thread(target=complete, args=(tid,)) for tid in ids]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert not errors
    assert all(todo.state == State.COMPLETED for todo in ts.todos)


def test_callback_outside_lock_does_not_deadlock():
    # The callback re-enters the toolset via get_all_todos(). If the callback
    # were called while the lock was held, this would deadlock on a plain Lock.
    seen = []

    def reentrant_callback(short_desc, desc, state):
        seen.append(ts.get_all_todos())

    ts = ToDoToolSet(callback=reentrant_callback)
    ts.add("task", "description")

    assert len(ts.todos) == 1
    assert len(seen) == 1
