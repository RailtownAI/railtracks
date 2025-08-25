import railtracks as rt
from railtracks.llm.response import Response, Stream 

llm = rt.llm.OpenAILLM("gpt-4o", stream=True)

mh = rt.llm.MessageHistory([rt.llm.UserMessage("give me a 50 word essay on LLMs")])

response = llm.chat(messages=mh)

assert isinstance(response, Stream)
assert response.streamer is not None

print(response.message_info)
for chunk in response.streamer:
    print(chunk.message)  

print(response.message_info)


