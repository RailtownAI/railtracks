# Build Your First Agent

In the [quickstart](https://docs.railtracks.org/documentation/getting_started/quickstart/index.md), you ran a ready-made agent. Now let's build your own step by step, starting from the simplest form and gradually adding more abilities.

## Simple LLM Agent

Start with minimal ingredients: a model + a system message

```python
SimpleLLM = rt.agent_node(
    llm=rt.llm.AnthropicLLM("claude-sonnet-5-5"),
    system_message="You are a helpful AI assistant."
)
```

Supported LLMs

Check out our full list of [supported providers](https://docs.railtracks.org/integrations/llms/providers/index.md)

## Adding Tool Calling

What if your agent needs real-world data? You will need to give it *tools*. This allows your agent to go beyond static responses and actually interact with the real world.

Creating a Tool

All you need is a Python function with docstring and the `rt.function_node` decorator

```python
# Use @rt.function_node decorator to convert your function into a RT tool
@rt.function_node
def your_function(example_input: str):
    """
    Your function description here.

    Args:
      example_input (str): The input string to process.

    """
    pass
```

[Learn more about tools](https://docs.railtracks.org/tutorials/concepts/tools/index.md)

```python
@rt.function_node
def weather_tool(city: str):
    """
    Returns the current weather for a given city.

    Args:
      city (str): The name of the city to get the weather for.
    """
    # Simulate a weather API call
    return f"{city} is sunny with a temperature of 25°C."

WeatherAgent = rt.agent_node(
    name="Weather Agent",
    llm=rt.llm.OpenAILLM("gpt-6-luna"),
    system_message="You are a helpful assistant that answers weather-related questions.",
    tool_nodes=[weather_tool],
)
```

Using MCP servers

MCP servers can be used as tools in the RT framework.

To connect to an MCP, please refer to our [guide](https://docs.railtracks.org/tutorials/concepts/mcp/index.md)

## Adding a Structured Output

Now that you've seen how to add tools. Let's look at your agent can respond with reliable typed outputs. Schemas give you reliable, machine-checked outputs you can safely consume in code, rather than brittle strings.

Defining a Schema

We use the Pydantic library to define structured data models.

```python
from pydantic import BaseModel, Field

class YourModel(BaseModel):
    # Use the Field parameter for more control. 
    parameter: str = Field(default="default_value", description="Your description of the parameter")
```

Visit the [pydantic docs](https://docs.pydantic.dev/latest/) to learn about what you can do with `BaseModel`'s

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

## Structured + Tool Calling

Often you will want the best of both worlds, an agent capable of both tool calling and responding in a structured format.

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

______________________________________________________________________

# Running Agents

Congratulations, you’ve now built agents that call tools, return structured outputs, and even combine both. Next, let’s actually run them and see them in action -> [Running your First Agent](https://docs.railtracks.org/tutorials/walkthroughs/ryfa/index.md).
