# Max Calls

`Max Calls` is a middleware that limits the number of calls to a node or model. This can be useful if you want tools to be called just once per workflow, or in general if you want to limit the number of calls to a tool.

```python
--8<-- "docs/scripts/prebuilt_middleware.py:max_calls"
```

Because it only controls the wrapped call, `Max Calls` works in both
`middleware=` (capping whole-node invocations) and `model_middleware=` (capping raw model calls inside the agent tool loop). The limit is enforced on the complete call in the selected slot.

### Workflow Run Scoping

The budget is scoped to each workflow run / session. When a new run begins (e.g. via `flow.invoke()` or `rt.call()`), the call counter starts fresh automatically.

### Shared Budgets Across Nodes

A single `MaxCalls` instance shared across multiple nodes enforces a combined budget:

```python
shared_budget = MaxCalls(max_calls=5)

ToolA = rt.function_node(func_a, middleware=[shared_budget])
ToolB = rt.function_node(func_b, middleware=[shared_budget])
```

Calls to either `ToolA` or `ToolB` accumulate against the same budget of 5.

A single instance may be shared by `function_node` and `agent_node` alike; both keep the instance you pass rather than a copy of it, so `call_count` and `reset()` on your handle act on the budget the nodes are actually spending.

### Inspecting and Resetting

You can inspect the current call count and reset the counter programmatically:

```python
budget = MaxCalls(max_calls=3)

# Inspect current spend (scoped to the active session)
print(budget.call_count)

# Reset counter for the current session
budget.reset()

# Reset counters for all sessions
budget.reset_all()
```

Read `call_count` outside a run and it reports the run that just finished, so you can check what a flow spent once `invoke()` returns. Counters for finished runs are retained for this, capped at the 64 most recent sessions.
