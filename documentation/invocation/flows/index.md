# Flows (Session Management)

In Railtracks, flows are the primary way to organize your agent runs. Think of a Flow as a blueprint that you invoke to start a run. A single Flow can be invoked multiple times to execute the same agentic process. This guide provides concrete examples to help you get started with Flows.

## Quickstart

To get started with Flows, you simply need to provide an entry point and a name.

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
