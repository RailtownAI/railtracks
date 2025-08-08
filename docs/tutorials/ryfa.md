# How to Run Your First Agent

Once you have defined your agent class you can then run your work flow and see results!

To begin you just have to use `call` for asynchronous flows or `call_sync` if it's s sequential flow. You simply pass your agent node as a parameter as well as the prompt as `user_input`:


### Example
```python
import railtracks as rt

response = rt.call_sync(
    weather_agent_class,
    user_input="Would you please be able to tell me the forecast for the next week?"
)

#Or if it's an async flow

async def main():
    return await rt.call(Agent)
```

Just like that you have ran your first agent! If you don't know about async, don't worry, you can keep reading and just use `call_sync` or click here to learn more.

---

## Customization and Configurability

Although it really is that simple to run your agent, you can do more of course. If you have a dynamic work flow you can delay parameters like `llm_model` and you can add a `SystemMessage` along with your prompt directly to `user_input` as a `MessageHistory` object.

### Example
```python
import railtracks as rt

weather_agent_class = rt.agent_node(
    tool_nodes={weather_tool},
    output_schema=weather_schema, 
)

system_message = rt.message.SystemMessage("You are a helpful assistant that answers weather-related questions.")
user_message = rt.message.UserMessage("Would you please be able to tell me the forecast for the next week?")

response = rt.call_sync(
    weather_agent_class,
    user_input=MessageHistory([system_message, user_message]),
    llm_model=rt.llm.AnthropicLLM("claude-3-5-sonnet-20241022"),
)
```

Should you pass `llm_model` to `agent_node` and then a different llm model to either call function, RailTracks will use the parameter passed in the call. If you pass `system_message` to `agent_node` and then another `system_message` to a call function, the system messages will be stacked.

### Example
```python

default_model = rt.llm.OpenAILLM("gpt-4o")
default_system_message = "You are a helpful assistant that answers weather-related questions."

weather_agent_class = rt.agent_node(
    tool_nodes={weather_tool},
    system_message=default_system_message,
    llm_model=default_model,
)

system_message = rt.message.SystemMessage("If not specified, the user is talking about Vancouver.")
user_message = rt.message.UserMessage("Would you please be able to tell me the forecast for the next week?")

response = await rt.call(
    weather_agent_class,
    user_input=MessageHistory([system_message, user_message]),
    llm_model=rt.llm.AnthropicLLM("claude-3-5-sonnet-20241022"),
)
```
In this example RailTracks will use claude rather than chatgpt and the system message will become
"You are a helpful assistant that answers weather-related questions. If not specified, the user is talking about Vancouver."

## Retrieving The Results of a Run

All agents return a response object which you can use to get the last message or the entire message history if you would prefer.

### Unstructured Response Example
```python

coding_agent_node = rt.agent_node()

system_message = rt.message.SystemMessage("You are an assistant that helps users write code and learn about coding.")
user_message = rt.message.UserMessage("Would you be able to help me figure out a good solution to running agentic flows?")

response = rt.call(
    coding_agent_node,
    user_input=MessageHistory([system_message, user_message]),
    llm_model=rt.llm.AnthropicLLM("claude-3-5-sonnet-20241022"),
)

answer_string = response.text()
message_history_object = response.message_history
```

### Structured Response Example
```python
from pydantic import BaseModel

class User(BaseModel):
    user_number : int
    age: int
    name: str

agent_node = rt.agent_node(
    output_schema=User,
    system_message=agent_message,
    llm_model=rt.llm.OpenAILLM("gpt-4o")

response = rt.call(
    agent_class,
    user_input=input_str
)

user_number = response.structured().user_number
message_history_object = response.message_history
```


