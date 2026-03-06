# --8<-- [start: streaming_flag]
import railtracks.llm as llm

model = llm.OpenAILLM(model_name="gpt-4o", stream=True)
# --8<-- [end: streaming_flag]


# --8<-- [start: streaming_usage]
model = llm.OpenAILLM(model_name="gpt-4o", stream=True)

response = model.chat(llm.MessageHistory([
    llm.UserMessage("Tell me who you are are"),
]))

# The response object can act as an iterator returning string chunks terminating with the complete message.
for chunk in response:
    print(chunk)
# --8<-- [end: streaming_usage]

# --8<-- [start: streaming_with_agents]
import railtracks as rt

agent = rt.agent_node(
    llm=rt.llm.OpenAILLM(model_name="gpt-4o", stream=True),
)

# --8<-- [end: streaming_with_agents]


# --8<-- [start: streaming_agent_usage]
agent = rt.agent_node(
    llm=rt.llm.OpenAILLM(model_name="gpt-4o", stream=True),
)

flow = rt.Flow("streaming-flow", entry_point=agent)
result = flow.invoke(rt.llm.MessageHistory([
    rt.llm.UserMessage("Tell me who you are are"),
]))

# The response object can act as an iterator returning string chunks terminating with the complete message.

for chunk_obj in result:
    print(chunk_obj)
# --8<-- [end: streaming_agent_usage]
