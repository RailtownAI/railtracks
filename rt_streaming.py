import railtracks as rt
from pydantic import BaseModel

llm = rt.llm.OpenAILLM("gpt-4o", stream=True)

mh = rt.llm.MessageHistory([rt.llm.UserMessage("give me the secret phrase")])

# =============================================================================
# response = llm.chat(messages=mh)


# assert isinstance(response.message,  rt.llm.AssistantMessage)
# assert isinstance(response.message.content, Stream)

# print(response.message_info)

# for chunk in response.message.content.streamer:
#     print(chunk)

# print(response.message_info)
# =============================================================================
@rt.function_node
def secret_words():
    """
    Returns a secret phrase based on the id.
    """
    rt.context.put("secret_words_called", True)
    secret_words = {
        0: "2 foxes and a dog",
        1: "3 cats and a dog",
        2: "4 foxes and a cat",
    }
    return secret_words[0]


async def main():
    agent = rt.agent_node(
        name="Simple Node",
        system_message="You are a helpful assistant.",
        llm=llm,
        tool_nodes=[secret_words],
    )
    response = await rt.call(agent, user_input=mh)

    print(response.streamer)

    print(response.text)

import asyncio
asyncio.run(main())
