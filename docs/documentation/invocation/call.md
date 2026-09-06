If you are familiar and comfortable with the `async/await` syntax and you do not require any configurations, you can simply use the `railtracks.call` API to invoke your agent:
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

The `call` API is also useful when you want to use agents as tools by having them wrapped within another a function (see [Agents as Tools](../agent_design/tools/agents_as_tools.md)). 

For configuration management such as context, observability through invocations, and other settings we recommend using [Flows](../invocation/flows.md).

## Continue a conversation across calls

Each call is stateless: Railtracks does not automatically send an earlier conversation to the next call. An agent response includes the complete conversation in `response.message_history`. To continue that conversation, copy the returned history, append the next user message, and pass it to the agent again:

```python
--8<-- "docs/scripts/documentation/message_history.py:direct_handoff"
```

`MessageHistory` behaves like a list. Copying the returned history before appending keeps the earlier response snapshot unchanged. Passing only `response.text` gives the next agent the previous answer without the messages that led to it.

## Share history between nodes in one run

When several nodes in the same flow need the conversation, store the latest history in [global context](../advanced/context.md). The context is available to every node in that run:

```python
--8<-- "docs/scripts/documentation/message_history.py:context_handoff"
```

Context ends with the run. If separate `flow.invoke(...)` or `flow.ainvoke(...)` calls should share a conversation, keep the latest `message_history` in your application or durable storage and pass it into the next run explicitly.
