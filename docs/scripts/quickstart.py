# --8<-- [start: setup]
import asyncio
import railtracks as rt

# To create your agent, you just need a model and a system message. 
Agent = rt.agent_node(
    llm=rt.llm.OpenAILLM("gpt-4o"),
    system_message="You are a helpful AI assistant."
)

# Now to call the Agent, we just need to use the `rt.call` function
async def main():
    result = await rt.call(
        Agent,
        "Hello, what can you do?"
    )
    return result

result = asyncio.run(main())
# --8<-- [end: setup]
print(result)