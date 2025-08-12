# How to Run Your First Agent

Once you have defined your agent class you can then run your work flow and see results!

To begin you just have to use `call` for asynchronous flows or `call_sync` if it's a sequential flow. You simply pass your agent node as a parameter as well as the prompt as `user_input`:


### Example
=== "Asynchronous"
    ```python

    response = await rt.call(
        WeatherAgent,
        user_input="Would you please be able to tell me the forecast for the next week?"
    )
    ```

=== "Synchronous"
    ```python

    response = rt.call_sync(
        WeatherAgent,
        user_input="Would you please be able to tell me the forecast for the next week?"
    )
    ```

!!! info "Asynchronous Execution"
    Since the `call` function is asynchronous and needs to be awaited, you should ensure that you are running this code within an asynchronous context.

    **Jupyter Notebooks**: If you are using in a notebook, you can run the code in a cell with `await` directly.

Just like that you have run your first agent!

---

## Customization and Configurability

Although it really is that simple to run your agent, you can do more of course. If you have a dynamic work flow you can delay parameters like `llm_model` and you can add a `SystemMessage` along with your prompt directly to `user_input` as a `MessageHistory` object.

### Example
```python
import railtracks as rt

WeatherAgent = rt.agent_node(
    tool_nodes={weather_node},
    schema=WeatherResponse, 
)

system_message = rt.llm.SystemMessage("You are a helpful assistant that answers weather-related questions.")
user_message = rt.llm.UserMessage("Would you please be able to tell me the forecast for the next week?")

response = rt.call(
    WeatherAgent,
    user_input=rt.llm.MessageHistory([system_message, user_message]),
    llm_model='claude-3-5-sonnet-20240620',
)
```

!!! info "Dynamic Runtime Configuration"

    If you pass `llm_model` to `agent_node` and then a different llm model to either `call` or `call_sync` functions, RailTracks will use the latter one. If you pass `system_message` to `agent_node` and then another `system_message` to a call function, the system messages will be stacked.

### Example
```python
import railtracks as rt

default_model = "gpt-4o"
default_system_message = "You are a helpful assistant that answers weather-related questions."

WeatherAgent = rt.agent_node(
    tool_nodes=[weather_node],
    system_message=default_system_message,
    llm_model=default_model,
)

system_message = rt.llm.SystemMessage("If not specified, the user is talking about Vancouver.")
user_message = rt.llm.UserMessage("Would you please be able to tell me the forecast for the next week?")

response = await rt.call(
    WeatherAgent,
    user_input=rt.llm.MessageHistory([system_message, user_message]),
    llm_model='claude-3-5-sonnet-20240620',
)
```
In this example RailTracks will use claude rather than chatgpt and the `system_message` will become
`"You are a helpful assistant that answers weather-related questions. If not specified, the user is talking about Vancouver."`

---

## Retrieving the Results of a Run

All agents return a response object which you can use to get the last message or the entire message history if you would prefer.

### Unstructured Response Example
```python
CodingAgent = rt.agent_node(...)

system_message = rt.message.SystemMessage("You are an assistant that helps users write code and learn about coding.")
user_message = rt.message.UserMessage("Would you be able to help me figure out a good solution to running agentic flows?")

response = await rt.call(
    CodingAgent,
    user_input=MessageHistory([system_message, user_message]),
    llm_model='claude-3-5-sonnet-20240620',
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

AgentNode = rt.agent_node(
    output_schema=User,
    system_message=agent_message,
    llm_model="gpt-4o"
)

response = await rt.call(
    AgentNode,
    user_input="some user input here"
)

user_number = response.structured().user_number
message_history_object = response.message_history
```