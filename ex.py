import railtracks as rt
from pydantic import BaseModel, Field
from railtracks.llm import MessageHistory, Message
model = rt.llm.OpenAILLM("gpt-4o")


def add(x: float, y: float):
    """A simple synchronous function that adds two numbers."""
    return x + y



resp = model.chat_with_tools(
    messages=MessageHistory([Message("Please use the tool you have to add 5 and 6", "user")]),
    tools=[rt.llm.Tool.from_function(add)],
)

print(resp)