# --8<-- [start: quickstart]
import railtracks as rt

agent = rt.agent_node(
    name="MyAgent",
    system_message="You are a helpful assistant that can answer questions and perform tasks.",
    llm=rt.llm.OpenAILLM("gpt-4o"),
)

# Create your flow by supplying an entry point.
flow = rt.Flow(name="MyFlow", entry_point=agent)

# And then invoke it with some input!
response = flow.invoke("What is the capital of France?")
print(response)
# --8<-- [end: quickstart]


# --8<-- [start: passing_configurations]
# Configuration options are passed as keyword arguments during initialization
configured_flow = rt.Flow(
    name="MyFlow",
    entry_point=agent,
    timeout=60,
    end_on_error=True,
    payload_callback=lambda payload: print("Payload:", payload)
)
# --8<-- [end: passing_configurations]


# --8<-- [start: injecting_context]
# Creating context shared across instances
context_flow = rt.Flow(
    name="MyFlow",
    entry_point=agent,
    context={"shared_key": "shared_value"}
)

# Injecting context into specific runs using .update_context()
context_injected_flow = context_flow.update_context({"run_specific_key": "run_specific_value"})
context_response = context_injected_flow.invoke("What is the value of shared_key and run_specific_key?")
# --8<-- [end: injecting_context]


# --8<-- [start: connecting]
# .connect() gives you a FlowConnection, which you invoke in place of the Flow.
connect_flow = rt.Flow(name="MyFlow", entry_point=agent, context={"shared_key": "shared_value"})
connection = connect_flow.connect()
connection_response = connection.invoke("What is the capital of France?")

# The run's context is still readable afterwards.
print(connection.context.get("shared_key"))
# --8<-- [end: connecting]


# --8<-- [start: connection_message_histories]
history_flow = rt.Flow(name="MyFlow", entry_point=agent)
history_connection = history_flow.connect()
history_response = history_connection.invoke("What is the capital of France?")

for history in history_connection.message_histories():
    print(history.node_name)
    for message in history.message_history:
        print(f"  {message.role}: {message.content}")
# --8<-- [end: connection_message_histories]


# --8<-- [start: connection_failure]
failure_flow = rt.Flow(name="MyFlow", entry_point=agent)
failure_connection = failure_flow.connect()

try:
    failure_connection.invoke("What is the capital of France?")
except Exception:
    # The context is readable even though the run raised.
    print("failed at stage:", failure_connection.context.get("stage", default="unknown"))
# --8<-- [end: connection_failure]


# --8<-- [start: connection_concurrent]
import asyncio

concurrent_flow = rt.Flow(name="MyFlow", entry_point=agent, context={"shared_key": "shared_value"})
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
# --8<-- [end: connection_concurrent]
