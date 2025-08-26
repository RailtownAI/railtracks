import railtracks as rt
from railtracks.llm.content import Stream 

llm = rt.llm.OpenAILLM("gpt-4o", stream=True)

mh = rt.llm.MessageHistory([rt.llm.UserMessage("give me a 50 word essay on LLMs")])

# =============================================================================
# response = llm.chat(messages=mh)


# assert isinstance(response.message,  rt.llm.AssistantMessage)
# assert isinstance(response.message.content, Stream)

# print(response.message_info)

# for chunk in response.message.content.streamer:
#     print(chunk)

# print(response.message_info)
# =============================================================================

agent = rt.agent_node(
    name="Simple Node",
    system_message="You are a helpful assistant.",
    llm_model=llm,
)
response = rt.call_sync(agent, user_input=mh)

print(response.streamer)

print(response.text)