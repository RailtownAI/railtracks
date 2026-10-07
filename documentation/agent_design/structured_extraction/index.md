## Adding a Structured Output

Now that you've seen how to add tools. Let's look at your agent can respond with reliable typed outputs. Schemas give you reliable, machine-checked outputs you can safely consume in code, rather than brittle strings.

```python
class WeatherResponse(BaseModel):
    temperature: float
    condition: str

StructuredWeatherAgent = rt.agent_node(
    name="Weather Agent",
    llm=rt.llm.OpenAILLM("gpt-6-luna"),
    system_message="You are a helpful assistant that answers weather-related questions.",
    output_schema=WeatherResponse,
)
```

Pydantic: Defining a Schema

We use [Pydantic](https://pydantic.dev/docs/validation/latest/get-started/) to define structured data models.

```python
from pydantic import BaseModel, Field

class YourModel(BaseModel):
    # Use the Field parameter for more control. 
    parameter: str = Field(default="default_value", description="Your description of the parameter")
```

Visit the [pydantic docs](https://docs.pydantic.dev/latest/) to learn about what you can do with `BaseModel`'s

## Structured + Tool Calling

Often you will want the best of both worlds, an agent capable of both tool calling and responding in a structured format. At the time of writing this, most LLMs do not support *structured output* and *tool calling* together. In `Railtracks` we support the following two ways of achieving this:

### 1. Implement the Separation

Using a [Flow](https://docs.railtracks.org/documentation/invocation/flows/index.md) you can separate out the tool calling and strucutred output steps. Here's an example how:

```python
async def flow_func(arg: str)->str:
    first_resp = await rt.call(ToolCallingAgent, arg)

    second_resp = await rt.call(StructuredAgent, first_step.message_history) # or pass in first_step.content
```

See [Message History](https://docs.railtracks.org/documentation/invocation/message_history/index.md) for how returned history can be passed safely between calls.

`ToolCallingAgent` vs `StructuredAgent`

As noted in the first section of this page, the pure `TooCallingAgent` should ***not*** be passed an `output_schema` for things to work optimally this way, and similarly the `StructuredAgent` should not have `tool_nodes` passed to it.

### 2. Abstracted Separation

In this way, Railtracks automatically implements the steps above for you. Simply need provide the `output_schema` and `tool_nodes` parameter to the same `agent_node` definition.

```python
WeatherToolCallAgent = rt.agent_node(
    name="Weather Agent",
    llm=rt.llm.OpenAILLM("gpt-6-luna"),
    system_message="You are a helpful assistant that answers weather-related questions.",
    tool_nodes=[weather_tool],
)

WeatherStructuredAgent = rt.agent_node(
    name="Weather Formatter Agent",
    llm=rt.llm.OpenAILLM("gpt-6-luna"),
    system_message="Extract the temperature and condition from the assistant's answer.",
    output_schema=WeatherResponse,
)

# Call the ToolCall agent first, then hand its answer to the structured agent, wrapped by an rt function
@rt.function_node
async def StructuredToolCallWeatherAgent(prompt: str):
    tool_response = await rt.call(WeatherToolCallAgent, user_input=prompt)
    return await rt.call(WeatherStructuredAgent, user_input=tool_response.content)
```
