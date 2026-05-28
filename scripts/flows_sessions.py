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