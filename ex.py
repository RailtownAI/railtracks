import railtracks as rt
from railtracks.llm.content import Stream

llm = rt.llm.OpenAILLM("gpt-4o", stream=True)
mh = rt.llm.MessageHistory([rt.llm.UserMessage("give me the secret phrase")])

response = llm.chat(messages=mh)
assert isinstance(response.message, rt.llm.AssistantMessage)
assert isinstance(response.message.content, Stream)

# Stream the response
for chunk in response.message.content.streamer:
    print(chunk)