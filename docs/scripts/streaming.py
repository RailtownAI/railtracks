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


# --8<-- [start: v2_streaming_agent]
import railtracks as rt

# Both the LLM and the agent must have stream=True.
agent = rt.agent_node(
    name="StreamingAgent",
    llm=rt.llm.OpenAILLM(model_name="gpt-4o", stream=True),
    system_message="You are a helpful assistant.",
    stream=True,
)
# --8<-- [end: v2_streaming_agent]


# --8<-- [start: astream_usage]
import railtracks as rt

agent = rt.agent_node(
    name="StreamingAgent",
    llm=rt.llm.OpenAILLM(model_name="gpt-4o", stream=True),
    system_message="You are a helpful assistant.",
    stream=True,
)

flow = rt.Flow(name="streaming-flow", entry_point=agent)

async for item in flow.astream("Tell me who you are."):
    if isinstance(item, str):
        print(item, end="", flush=True)   # chunk arrives in real time
    else:
        final = item                       # StringResponse — always the last item
# --8<-- [end: astream_usage]


# --8<-- [start: v2_streaming_callback]
import railtracks as rt

agent = rt.agent_node(
    name="StreamingAgent",
    llm=rt.llm.OpenAILLM(model_name="gpt-4o", stream=True),
    system_message="You are a helpful assistant.",
    stream=True,
)

# Chunks arrive in real time via broadcast_callback while ainvoke() is still running.
# The callback may be a plain def or an async def.
async def on_chunk(chunk: str) -> None:
    print(chunk, end="", flush=True)

# ainvoke() returns StringResponse only after the last chunk has arrived.
result = await rt.Flow(
    name="streaming-flow",
    entry_point=agent,
    broadcast_callback=on_chunk,
).ainvoke("Tell me who you are.")

print(result.text)   # same content, fully assembled
# --8<-- [end: v2_streaming_callback]
