# Flows

A **Flow** is a named, reusable entry point for an agent graph. It binds one [entry point](#entry-point) node to a fixed set of runtime options, such as context, a timeout, an error policy and callbacks, so the same agentic process can be invoked as many times as you like with each [run](#run) isolated from the others.

A Flow is the intended top level of a Railtracks program, because everything it provides is scoped to the Flow rather than to a single call: context shared across runs, a timeout over the whole graph, and a connection you can inspect once a run has finished. Inside a Flow, nodes reach one another through [direct invocation](call.md). This guide provides concrete examples to help you get started with Flows.

!!! note "Two senses of the word 'flow'"
    Capital-F **Flow** always means the `rt.Flow` object described on this page. Lowercase "flow" appears elsewhere in these docs for the *shape* of an agent graph, as in "keep your flows linear", which describes an architecture rather than an object.

## Quickstart
To get started with Flows, you simply need to provide an [entry point](#entry-point) and a name.

```python
--8<-- "docs/scripts/flows_sessions.py:quickstart"
```

### Entry Point

The **entry point** is the node a Flow starts from, given as `entry_point=`. It is the only node the Flow invokes itself; every other node in the graph is reached from it, either because an agent chose it as a tool or because your code called it with [`rt.call`](call.md).

Any node can be an entry point. An [agent node](../agent_design/overview.md#agent-node) makes the Flow a single agent, while a [function node](../agent_design/tools/function_tools.md#what-a-function-node-is) makes it a multi-step process whose order your own Python controls, as in [Sequential Flows](../../tutorials/concepts/architectures/sequential.md).

## Run

A **run** is one execution of a Flow, started by `invoke` or `ainvoke`. It is the scope Railtracks uses for nearly everything that is not part of an agent's own definition: [context](../advanced/context.md) lives for the length of a run, a Flow's `timeout` applies to the whole run, and per-run budgets such as [`MaxCalls`](../agent_design/middleware/prebuilt/list/max_calls.md) start fresh at the beginning of each one.

Runs of the same Flow never share state. Invoking a Flow twice, or invoking it concurrently, gives each run its own context and its own graph of node invocations.

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