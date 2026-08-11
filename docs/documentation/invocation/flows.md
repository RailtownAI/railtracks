# Flows (Session Management)
In Railtracks, flows are the primary way to organize your agent runs. Think of a Flow as a blueprint that you invoke to start a run. A single Flow can be invoked multiple times to execute the same agentic process. This guide provides concrete examples to help you get started with Flows.

## Quickstart
To get started with Flows, you simply need to provide an entry point and a name.

```python
--8<-- "docs/scripts/flows_sessions.py:quickstart"
```

## Passing Configuration
If you want to apply configurations scoped to a specific Flow, you can pass them in during the Flow's creation.

```python
--8<-- "docs/scripts/flows_sessions.py:passing_configurations"
```

## Injecting Context
Sometimes you may want generic context items to be available across all runs of a Flow. In other cases, you might want context scoped to a specific run (or injected at runtime).

```python
--8<-- "docs/scripts/flows_sessions.py:injecting_context"
```

!!! warning
    The context dictionaries used by Flows are passed by value. If a specific run mutates its context dictionary, those changes will not affect the original context or be passed to other runs.

## Inspecting a Run
`invoke` and `ainvoke` return only the flow's result, so anything a run built up along the way is gone once it finishes. Use `flow.connect()` when you need more than the result. It returns a `FlowConnection`, which you invoke in place of the Flow.

```python
--8<-- "docs/scripts/flows_sessions.py:connecting"
```

Nothing about your flow or its return type has to change, and the plain `invoke`/`ainvoke` path is unaffected.

### Message Histories
`connection.message_histories()` gives you every model conversation in the run, in the order the runs were recorded. This includes nested agents: an `LLMResponse` carries only its own history, so a flow that delegates to sub-agents cannot surface theirs through its return value.

```python
--8<-- "docs/scripts/flows_sessions.py:connection_message_histories"
```

Each entry is a `NodeMessageHistory` with `node_name`, `node_id`, `request_id` and `message_history`. Nodes that made no model calls are omitted. Nodes called concurrently have no guaranteed order between them.

### Failed Runs
The accessors stay readable after an invocation raises, which is often when you most want them.

```python
--8<-- "docs/scripts/flows_sessions.py:connection_failure"
```

### Concurrency
A connection handles one invocation at a time and raises if you start a second while the first is in flight. Open a connection per concurrent run.

```python
--8<-- "docs/scripts/flows_sessions.py:connection_concurrent"
```

!!! note
    A connection can be invoked repeatedly. Its accessors always describe the **most recent** invocation.

<!-- 
### Reaching Further
`connection.session` exposes the underlying `Session` for anything without a dedicated accessor.

```python
connection.session.info      # the run graph: nodes, requests, timing
connection.session.payload() # the JSON that save_state writes
```

!!! warning
    `Session.info` and `Session.payload()` expose the run's state representation, whose shape is not yet stable. Prefer an accessor on `FlowConnection` where one exists. -->