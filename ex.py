import railtracks as rt
from pydantic import BaseModel, Field
from railtracks.llm import MessageHistory, Message
model = rt.llm.OpenAILLM("gpt-4o")


def error_function(x: int) -> str:
    """
    Args:
        x (int): The input number to the function

    Returns:
        str: The result of the function.
    """
    rt.context.put("magic_test_called", True)
    return str(1 / x)

agent = rt.agent_node(
    tool_nodes={rt.function_node(error_function)},
    name="Error Function Agent",
    system_message="You are a helpful assistant that can call the tools available to you to answer user queries",
    llm_model=model,
)

with rt.Session():
    response = rt.call_sync(    
        agent, 
        "Please use the tool you have and invoke it with 0"
    )   
    print(response.content)
