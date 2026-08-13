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
flow = rt.Flow(
    name="MyFlow",
    entry_point=agent,
    timeout=60,
    end_on_error=True, 
    payload_callback=lambda payload: print("Payload:", payload)
)
# --8<-- [end: passing_configurations]


# --8<-- [start: injecting_context]
# Creating context shared across instances
flow = rt.Flow(
    name="MyFlow",
    entry_point=agent,
    context={"shared_key": "shared_value"}
)

# Injecting context into specific runs using .update_context()
context_injected_flow = flow.update_context({"run_specific_key": "run_specific_value"})
response = context_injected_flow.invoke("What is the value of shared_key and run_specific_key?")
# --8<-- [end: injecting_context]


# --8<-- [start: connecting]
# .connect() gives you a FlowConnection, which you invoke in place of the Flow.
connection = flow.connect()
response = connection.invoke("What is the capital of France?")

# The run's context is still readable afterwards.
print(connection.context.get("shared_key"))
# --8<-- [end: connecting]


# --8<-- [start: connection_message_histories]
connection = flow.connect()
response = connection.invoke("What is the capital of France?")

for history in connection.message_histories():
    print(history.node_name)
    for message in history.message_history:
        print(f"  {message.role}: {message.content}")
# --8<-- [end: connection_message_histories]


# --8<-- [start: connection_failure]
connection = flow.connect()

try:
    connection.invoke("What is the capital of France?")
except Exception:
    # The context is readable even though the run raised.
    print("failed at stage:", connection.context.get("stage", default="unknown"))
# --8<-- [end: connection_failure]


# --8<-- [start: connection_concurrent]
import asyncio

connections = []
futures = []

# One connection per concurrent run.
for question in ["Capital of France?", "Capital of Japan?", "Capital of Peru?"]:
    connection = flow.connect()
    connections.append(connection)
    futures.append(connection.ainvoke(question))

results = await asyncio.gather(*futures)

for connection in connections:
    print(connection.session_id, connection.context.get("shared_key"))
# --8<-- [end: connection_concurrent]