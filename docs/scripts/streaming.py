# --8<-- [start: streaming_usage]
import asyncio

import railtracks.llm as llm


async def main():
    model = llm.OpenAILLM(model_name="gpt-4o")

    messages = llm.MessageHistory([
        llm.UserMessage("Tell me who you are."),
    ])

    # `astream_chat` yields `str` token chunks as they arrive, followed by a single
    # final `Response` object containing the complete message (and usage info).
    async for item in model.astream_chat(messages):
        if isinstance(item, str):
            print(item, end="")  # token chunk
        else:
            print("\n\nfinal response:", item.text)  # the terminal Response


asyncio.run(main())
# --8<-- [end: streaming_usage]
