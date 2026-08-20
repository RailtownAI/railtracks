# Direct Invocation (`rt.call`)

**Direct invocation** means passing a [Node](../agent_design/overview.md#node), including an [Agent Node](../agent_design/overview.md#agent-node), directly to `await rt.call(...)` and awaiting its output. Python code decides when and how the call runs, whether it is a top-level call or is nested inside another Node or a [Flow](flows.md) entry point.

Railtracks still runs the Node through its normal execution and middleware machinery. For a top-level call, it creates the required execution context internally; application code does not need to construct or manage that internal state.

Use direct invocation when you:

- need a one-off asynchronous result;
- want to control sequential or parallel calls with normal Python `async`/`await`; or
- only need the returned value, rather than reusable Flow configuration or post-run inspection.

For example, invoke an Agent Node and use its response immediately:
```python
import railtracks as rt

resp = await rt.call(AgentName, "user message to the agent")
```
!!! warning "async context"
    The above code snippet will work in an `async` context such as Jupyter notebooks. In a python script, it needs to be wrapped as follows:
    ```python
    from asyncio import run
    import railtracks as rt

    async def outer_func(...):
        resp = await rt.call(AgentName, "user message to the agent")

    run(outer_func(...))
    ```

The `call` API is also useful when you want to use agents as tools by wrapping them in another function (see [Agents as Tools](../agent_design/tools/agents_as_tools.md)).

Wrap the entry point in a [Flow](flows.md) when you need a named, reusable entry point with Flow-scoped configuration or context, synchronous invocation, or inspection through a `FlowConnection`.
