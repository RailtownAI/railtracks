# To Do Tooling
A common addition to your agent is a tool for tracking and planning todos. Railtracks provides a built-in tool for this purpose that you can drop into your agent right away.

## Usage 
Adding the todo tool to your agent is super easy.

```python 
--8<-- "docs/scripts/todos.py:todos"
```

!!! Warning
    Todos are scoped to the `ToDoToolSet` instance. All tools returned from the same instance share one list. To maintain separate todo lists for different agents, create a separate `ToDoToolSet` instance for each.

You may want to add details around how to use the todos in your prompt. We provide a simple helper function to describe how to use it:

```python
--8<-- "docs/scripts/todos.py:todo_prompt"
```

## Todo States

Each todo moves through a set of states that signal where it is in the agent's work. The LLM reads these states back from the view tools to understand what still needs doing.

| State | Value | Meaning to the LLM |
|---|---|---|
| `NOT_STARTED` | `not_started` | Planned but not yet begun. The default when a todo is added. |
| `IN_PROGRESS` | `in_progress` | The agent is actively working on this task right now. |
| `COMPLETED` | `completed` | The task finished successfully. No further action needed. |
| `FAILED` | `failed` | The task was attempted but could not be completed. Surfaced by `get_failed_todos()` and `get_incomplete_todos()` so the agent can decide whether to retry or create a replacement task. |
| `NO_LONGER_PLANNED` | `no_longer_planned` | The task was dropped without being attempted or failing — scope changed, made redundant, etc. Excluded from all standard views so it does not clutter the active plan. |

`COMPLETED` and `FAILED` are both terminal — the agent should not transition out of them. `NO_LONGER_PLANNED` is also terminal and is intentionally invisible to the agent's regular reads.

## Common Use Case

When an agent receives a multi-step task it will follow a consistent lifecycle with the todo tools: **plan first, then execute**.

### Planning phase

Before touching any work, the agent adds every subtask it has identified. The `get_all_todos()` call captures the identifiers it needs for subsequent calls.

```python
# Agent calls: add()
add(short_description="fetch_data", description="Pull the latest sales records from the database")
add(short_description="clean_data", description="Remove duplicates and normalise column types")
add(short_description="generate_report", description="Summarise findings and write the output CSV")

# Agent calls: get_all_todos() to retrieve identifiers before any id-based call
get_all_todos()
# → [
#     "(140234...) [not_started] fetch_data: Pull the latest sales records from the database",
#     "(140235...) [not_started] clean_data: Remove duplicates and normalise column types",
#     "(140236...) [not_started] generate_report: Summarise findings and write the output CSV",
#   ]
```

### Execution phase

The agent marks each todo in-progress when it starts, then transitions it to one of three terminal states depending on the outcome.

```python
start_todo_by_id(todo_id=140234)
# → "Successfully started todo:\n(140234...) [in_progress] fetch_data: ..."

# task succeeds
complete_todo_by_id(todo_id=140234)
# → "Successfully completed todo:\n(140234...) [completed] fetch_data: ..."

# task cannot be completed
fail_todo_by_id(todo_id=140235)
# → "Successfully marked todo as failed:\n(140235...) [failed] clean_data: ..."

# task is no longer needed (not a failure — just dropped)
no_longer_plan_todo_by_id(todo_id=140236)
# → "Successfully marked todo as no longer planned:\n(140236...) [no_longer_planned] generate_report: ..."

# abandon the entire remaining plan at once
make_all_no_longer_planned()
# → "Marked 2 todo(s) as no longer planned."
```

Todos marked `no_longer_planned` are silently excluded from `get_all_todos()`, `get_incomplete_todos()`, and `pretty_dashboard()`. `get_failed_todos()` is available for surfacing tasks that need attention.

### Connecting todos to a larger system

The `callback` parameter fires every time a new todo is added, letting the outer system react in real time — for example to push live progress to a UI, write to a database, or trigger a notification.

```python
--8<-- "docs/scripts/todos.py:todo_callback"
```

You can also inspect the todo list directly at any point via the `ToDoToolSet` instance — useful for logging, assertions, or driving downstream logic once the agent finishes.

```python
--8<-- "docs/scripts/todos.py:todo_inspection"
```