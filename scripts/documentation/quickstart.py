# --8<-- [start: setup]
import railtracks as rt

# To create your agent, you just need a model and a system message. 
Agent = rt.agent_node(
    llm=rt.llm.OpenAILLM("gpt-5"),
    system_message="You are a helpful AI assistant."
)


# Create your flow and set the entry point to the function we just created. 
# Then we can invoke the flow with a the input to the function node. 
flow = rt.Flow("Quickstart Example", entry_point=Agent)

result = flow.invoke("Hello, what can you do?")

# --8<-- [end: setup]
print(result)