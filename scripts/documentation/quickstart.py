# --8<-- [start: setup]
import railtracks as rt

# To create your agent, you just need a model and a system message. 
Agent = rt.agent_node(
    llm=rt.llm.OpenAILLM("gpt-5"),
    system_message="You are a helpful AI assistant."
)

# Create a function node that will be the entry point of our flow. 
# This is where we will call our Agent.
@rt.function_node
async def main(message: str):

    # Now to call the Agent, we just need to use the `rt.call` function
    result = await rt.call(
        Agent,
        message,
    )
    return result

# Create your flow and set the entry point to the function we just created. 
# Then we can invoke the flow with a the input to the function node. 
flow = rt.Flow("Quickstart Example", entry_point=main)

result = flow.invoke("Hello, what can you do?")

# --8<-- [end: setup]
print(result)