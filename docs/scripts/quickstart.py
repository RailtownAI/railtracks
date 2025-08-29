# --8<-- [start: setup]
import railtracks as rt

# To create your agent, you just need a model and a system message. 
CreativeThinker = rt.agent_node(
    llm=rt.llm.OpenAILLM("gpt-4o"),
    system_message=(
        "You are creative thinker who uses big words to answer user queries. Your response should be short but elegant. "
    ),
)
# --8<-- [end: setup]

# --8<-- [start: async_main]
import asyncio

# Now to call Creative Thinker, we just need to use the `rt.call` function
async def main():
    result = await rt.call(
        CreativeThinker,
        "What are your thoughts on the legacy of Artificial Intelligence?"
    )
    return result

result = asyncio.run(main())
# --8<-- [end: async_main]
print(result)