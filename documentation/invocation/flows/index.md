# Flows

A **Flow** is a named, reusable entry point for an agent graph. It binds one [entry point](#entry-point) node to a fixed set of runtime options, such as context, a timeout, an error policy and callbacks, so the same agentic process can be invoked as many times as you like with each [run](#run) isolated from the others.

A Flow is the intended top level of a Railtracks program, because everything it provides is scoped to the Flow rather than to a single call: a starting context copied into every run, a timeout over the whole graph, and a connection you can inspect once a run has finished. Inside a Flow, nodes reach one another through [direct invocation](https://docs.railtracks.org/documentation/invocation/call/index.md). This guide provides concrete examples to help you get started with Flows.

Two senses of the word 'flow'

Capital-F **Flow** always means the `rt.Flow` object described on this page. Lowercase "flow" appears elsewhere in these docs for the *shape* of an agent graph, as in "keep your flows linear", which describes an architecture rather than an object.

## Quickstart

To get started with Flows, you simply need to provide an [entry point](#entry-point) and a name.

```python
import railtracks as rt

MyAgent = rt.agent_node(
    name="MyAgent",
    system_message="You are a helpful assistant that can answer questions and perform tasks.",
    llm=rt.llm.OpenAILLM("gpt-6-luna"),
)

# Create your flow by supplying an entry point.
flow = rt.Flow(name="MyFlow", entry_point=MyAgent)

# And then invoke it with some input!
response = flow.invoke("What is the capital of France?")
print(response.content)
```

### Entry Point

The **entry point** is the node a Flow starts from, given as `entry_point=`. It is the only node the Flow invokes itself; every other node in the graph is reached from it, either because an agent chose it as a tool or because your code called it with [`rt.call`](https://docs.railtracks.org/documentation/invocation/call/index.md).

Any node can be an entry point. An [agent node](https://docs.railtracks.org/documentation/agent_design/overview/#agent-node) makes the Flow a single agent, while a [function node](https://docs.railtracks.org/documentation/agent_design/tools/function_tools/#what-a-function-node-is) makes it a multi-step process whose order your own Python controls, as in [Sequential Flows](https://docs.railtracks.org/tutorials/concepts/architectures/sequential/index.md).

## Run

A **run** is one execution of a Flow, started by `invoke` or `ainvoke`. It is the scope Railtracks uses for nearly everything that is not part of an agent's own definition: [context](https://docs.railtracks.org/documentation/advanced/context/index.md) lives for the length of a run, a Flow's `timeout` applies to the whole run, and per-run budgets such as [`MaxCalls`](https://docs.railtracks.org/documentation/agent_design/middleware/prebuilt/list/max_calls/index.md) start fresh at the beginning of each one.

Runs of the same Flow never share state. Invoking a Flow twice, or invoking it concurrently, gives each run its own context and its own graph of node invocations.

## Passing Configuration

If you want to apply configurations scoped to a specific Flow, you can pass them in during the Flow's creation.

```python
# Configuration options are passed as keyword arguments during initialization
configured_flow = rt.Flow(
    name="MyFlow",
    entry_point=MyAgent,
    timeout=60,
    end_on_error=True,
    payload_callback=lambda payload: print("Payload:", payload)
)
```

## Injecting Context

Sometimes you may want generic context items to be available across all runs of a Flow. In other cases, you might want context scoped to a specific run (or injected at runtime).

```python
# Creating context shared across instances
context_flow = rt.Flow(
    name="MyFlow",
    entry_point=MyAgent,
    context={"shared_key": "shared_value"}
)

# Injecting context into specific runs using .update_context()
context_injected_flow = context_flow.update_context({"run_specific_key": "run_specific_value"})
context_response = context_injected_flow.invoke("What is the value of shared_key and run_specific_key?")
```

Warning

The context dictionaries used by Flows are passed by value. If a specific run mutates its context dictionary, those changes will not affect the original context or be passed to other runs.

## Inspecting a Run

`invoke` and `ainvoke` return only the flow's result, so anything a run built up along the way is gone once it finishes. Use `flow.connect()` when you need more than the result. It returns a `FlowConnection`, which you invoke in place of the Flow.

```python
# .connect() gives you a FlowConnection, which you invoke in place of the Flow.
connect_flow = rt.Flow(name="MyFlow", entry_point=MyAgent, context={"shared_key": "shared_value"})
connection = connect_flow.connect()
connection_response = connection.invoke("What is the capital of France?")

# The run's context is still readable afterwards.
print(connection.context.get("shared_key"))
```

Nothing about your flow or its return type has to change, and the plain `invoke`/`ainvoke` path is unaffected.

### Message Histories

`connection.message_histories()` gives you every model conversation in the run, in the order the runs were recorded. This includes nested agents: an `LLMResponse` carries only its own history, so a flow that delegates to sub-agents cannot surface theirs through its return value.

```python
history_flow = rt.Flow(name="MyFlow", entry_point=MyAgent)
history_connection = history_flow.connect()
history_response = history_connection.invoke("What is the capital of France?")

for history in history_connection.message_histories():
    print(history.node_name)
    for message in history.message_history:
        print(f"  {message.role}: {message.content}")
```

Each entry is a `NodeMessageHistory` with `node_name`, `node_id`, `request_id` and `message_history`. Nodes that made no model calls are omitted. Nodes called concurrently have no guaranteed order between them.

### Failed Runs

The accessors stay readable after an invocation raises, which is often when you most want them.

```python
failure_flow = rt.Flow(name="MyFlow", entry_point=MyAgent)
failure_connection = failure_flow.connect()

try:
    failure_connection.invoke("What is the capital of France?")
except Exception:
    # The context is readable even though the run raised.
    print("failed at stage:", failure_connection.context.get("stage", default="unknown"))
```

### Concurrency

A connection handles one invocation at a time and raises if you start a second while the first is in flight. Open a connection per concurrent run.

```python
import asyncio

concurrent_flow = rt.Flow(name="MyFlow", entry_point=MyAgent, context={"shared_key": "shared_value"})
connections = []
futures = []

# One connection per concurrent run.
for question in ["Capital of France?", "Capital of Japan?", "Capital of Peru?"]:
    concurrent_connection = concurrent_flow.connect()
    connections.append(concurrent_connection)
    futures.append(concurrent_connection.ainvoke(question))

results = await asyncio.gather(*futures)

for conn in connections:
    print(conn.session_id, conn.context.get("shared_key"))
```

Note

A connection can be invoked repeatedly. Its accessors always describe the **most recent** invocation.
