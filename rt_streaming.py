import railtracks as rt
from pydantic import BaseModel

llm = rt.llm.OpenAILLM("gpt-4o", stream=True)

mh = rt.llm.MessageHistory([rt.llm.UserMessage("give me the answer to the universe")])

# =============================================================================
# response = llm.chat(messages=mh)


# assert isinstance(response.message,  rt.llm.AssistantMessage)
# assert isinstance(response.message.content, Stream)

# print(response.message_info)

# for chunk in response.message.content.streamer:
#     print(chunk)

# print(response.message_info)
# =============================================================================
class SimpleSchema(BaseModel):
    val: int

async def main():
    agent = rt.agent_node(
        name="Simple Node",
        system_message="You are a helpful assistant.",
        llm=llm,
        output_schema=SimpleSchema,
    )
    response = await rt.call(agent, user_input=mh)

    print(response.streamer)

    print(response.structured)

import asyncio
asyncio.run(main())
