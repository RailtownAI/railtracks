# Direct Invocation

**Direct invocation** is calling a node yourself with `await rt.call(...)` instead of letting an agent decide to call it. It is how the steps inside a [Flow](flows.md) are composed: the Flow's [entry point](flows.md#entry-point) is your own `async` function, and each step in it is an `rt.call` whose result you use like any other awaited value.

```python
import railtracks as rt

resp = await rt.call(AgentName, "user message to the agent")
```

Because these are ordinary `await` expressions, the control flow stays yours. Await them one after another to fix an order (see [Sequential Flows](../../tutorials/concepts/architectures/sequential.md)), gather them with `asyncio.gather` to run steps concurrently, or branch on a result before deciding what to call next.

!!! warning "async context"
    The above code snippet will work in an `async` context such as Jupyter notebooks. In a python script, it needs to be wrapped as follows:
    ```python
    from asyncio import run
    import railtracks as rt

    async def outer_func(...):
        resp = await rt.call(AgentName, "user message to the agent")

    run(outer_func(...))
    ```

The `call` API is also useful when you want to use agents as tools by having them wrapped within another a function (see [Agents as Tools](../agent_design/tools/agents_as_tools.md)).

!!! tip "Start from a Flow"
    `rt.call` does work as the top level of a script, where Railtracks builds the surrounding machinery for you with default settings. What you give up is everything that is configured on the Flow: context shared across runs, `timeout`, `end_on_error`, broadcast and payload callbacks, and the `flow.connect()` handle for inspecting a [run](flows.md#run) after it finishes. Past a quick experiment, wrap your entry point in a [Flow](flows.md) and keep `rt.call` for the steps inside it.
