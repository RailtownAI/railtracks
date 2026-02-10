# --8<-- [start: setup]
import railtracks as rt

# To create your agent, you just need a model and a system message. 
Agent = rt.agent_node(
    llm=rt.llm.OpenAILLM("gpt-4o"),
    system_message="You are a helpful AI assistant."
)

# Now to call the Agent, we just need to use the `rt.call` function
@rt.function_node
async def main(message: str):
    result = await rt.call(
        Agent,
        message,
    )
    return result

flow = rt.Flow("Quickstart Example", entry_point=main)

result = flow.invoke("Hello, what can you do?")

# --8<-- [end: setup]
print(result)