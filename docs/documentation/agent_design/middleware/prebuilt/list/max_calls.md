# Max Calls

`Max Calls` is a middleware that limits the number of calls to a node or model. This can be useful if you want tools to be called just once per workflow, or in general if you want to limit the number of calls to a tool.

```python
--8<-- "docs/scripts/prebuilt_middleware.py:max_calls"
```

Because it only controls the wrapped call, `Max Calls` works in both
`middleware=` (capping whole-node invocations) and `model_middleware=` (capping raw model calls inside the agent tool loop). The limit is enforced on the complete call in the selected slot.

### Workflow Run Scoping

The budget is scoped to the session, not to the node. Every call made during one session spends the same budget, however deeply nested, and each new session starts fresh. `flow.invoke()` opens a session per invocation, so a node budgeted at 3 gets 3 calls per run rather than 3 for the life of the process.

!!! warning "A bare top-level `rt.call()` is its own run"

    Called outside any flow, `rt.call()` opens a short-lived session for that single call, so a budget shared across several top-level calls resets on each and never fires. Put the calls behind one entry point and invoke it once to hold a single budget across all of them:

    ```python
    @rt.function_node
    async def spend_the_budget() -> None:
        """Both calls draw on the same budget."""
        await rt.call(tool, x="a")
        await rt.call(tool, x="b")


    rt.Flow("budgeted-run", entry_point=spend_the_budget).invoke()
    ```

    Inside a flow, `rt.call()` joins the running session and spends its budget as expected. This only bites bare top-level calls.

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

Read `call_count` outside a run and it reports the run that just finished, so you can check what a flow spent once `invoke()` returns.

!!! warning "Only the 64 most recent sessions stay readable"

    Finished runs' counters are kept so they can be inspected afterwards, but a single `MaxCalls` retains at most the 64 most recently used sessions and evicts the oldest beyond that. This bounds memory for a long-lived instance; it does not limit how many runs may overlap. Reading `call_count` for a session evicted that long ago reports `0`, so capture the value you care about near the end of the run rather than much later.
