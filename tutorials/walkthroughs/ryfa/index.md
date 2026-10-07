# How to Run Your First Agent

## Calling the Agent directly

Once you have defined your agent class ([Build Your First Agent](https://docs.railtracks.org/tutorials/walkthroughs/byfa/index.md)) you can then run your workflow and see results!

To begin you just have to use **`call`** method from Railtracks. This is an asynchronous method so you will need to run it in an async context.

```python
flow = rt.Flow("weather-flow", entry_point=StructuredToolCallWeatherAgent)
response = flow.invoke("What is the forecast for Vancouver today?")
```

Agent input options

There are multiple ways to provide input to your agent.

single user message

If you'd like to simply provide a single user message, you can pass it as a string directly to the **`call`**

few-shot prompting

If you want to provide a few-shot prompt, you can pass a list of messages to the `call` functions, with the specific message for each role being passed as an input to its specific role ie (**`rt.llm.UserMessage`** for user, **`rt.llm.AssistantMessage`** for assistant):

```python
normal_weather_flow = rt.Flow("weather-flow", entry_point=WeatherAgent)
normal_weather_flow.invoke("What is the forecast for BC today? Please specify the specific city in BC you're interested in Vancouver.")
```

Asynchronous Execution

Since the **`call`** function is asynchronous and needs to be awaited, you should ensure that you are running this code within an asynchronous context like the **`main`** function in the code snippet above.

**Jupyter Notebooks**: If you are using in a notebook, you can run the code in a cell with **`await`** directly.

For more info on using `async/await` in RT, see [Async/Await in Python](https://docs.railtracks.org/tutorials/concepts/async_await/index.md).

Dynamic Runtime Configuration

If you pass `llm` to `agent_node` and then a different llm model to `call` function, Railtracks will use the latter one. If you pass `system_message` to `agent_node` and then another `system_message` to `call`, the system messages will be stacked.

Example

```python
    import railtracks as rt
    from pydantic import BaseModel

    class WeatherResponse(BaseModel):
        temperature: float
        condition: str


    system_message = rt.llm.SystemMessage(
        "You can also geolocate the user"
    )
    user_message = rt.llm.UserMessage(
        "Would you please be able to tell me the forecast for the next week?"
    )

    structureed_weather_flow = rt.Flow("weather-flow", entry_point=StructuredToolCallWeatherAgent)
    response = structureed_weather_flow.invoke("Would you please be able to tell me the forecast for the next week?")
```

In this example Railtracks will use claude rather than chatgpt and the `system_message` will become `"You are a helpful assistant that answers weather-related questions. If not specified, the user is talking about Vancouver."`

Just like that you have run your first agent!

All agents return a response object which you can use to get the last message or the entire message history if you would prefer.

Reponse of a Run

In the **unstructured response** example, the last message from the agent and the entire message history can be accessed using the `content` and `message_history` attributes of the response object, respectively.

```python
print(f"Last Message: {response.content}")
print(f"Message History: {response.message_history}")
```

WeatherResponse

```python
class WeatherResponse(BaseModel):
    temperature: float
    condition: str
```

In the structured response example, the `output_schema` parameter is used to define the expected output structure. The response can then be accessed using the `content` attribute, which holds an instance of your schema.

```python
print(f"Condition: {response.content.condition}")
print(f"Temperature: {response.content.temperature}")
```
