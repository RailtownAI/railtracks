# Message History

Each call is stateless: Railtracks does not automatically send an earlier conversation to the next call. An agent response includes the conversation in `response.message_history`, excluding the system message. Railtracks prepends the target agent's system message on each call, so passing the returned history back does not accumulate duplicate system messages.

The examples below use this agent:

```python
--8<-- "docs/scripts/documentation/message_history.py:message_history_setup"
```

## Continue a conversation across calls

Copy the returned history, append the next user message, and pass it to the agent again:

```python
--8<-- "docs/scripts/documentation/message_history.py:direct_handoff"
```

`MessageHistory` behaves like a list. Copying the returned history before appending keeps the earlier response snapshot unchanged. Passing only `response.text` gives the next agent the previous answer without the messages that led to it.

## Share history between nodes in one run

When several nodes in the same flow need the conversation, store the latest history in [global context](../advanced/context.md). The context is available to every node in that run:

```python
--8<-- "docs/scripts/documentation/message_history.py:context_handoff"
```

This get → copy → append → put pattern assumes one turn at a time; concurrent turns must use separate context keys or synchronize access so one turn does not overwrite another turn's history.

Context ends with the run. If separate `flow.invoke(...)` or `flow.ainvoke(...)` calls should share a conversation, keep the latest `message_history` in your application or durable storage and pass it into the next run explicitly.
