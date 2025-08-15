# Controlling Flows and Wrapping Nodes

RailTracks makes it easy to create custom agents with access to tools they can call to complete tasks. But what if you want to use agents themselves as tools? In this section, we’ll explore more complex flows and how RailTracks gives you control over them.

To start, let’s look at the simplest case: an agent that uses another agent as a tool.

### Example
```python
import railtracks as rt
from pydantic import BaseModel

#As before, we will create our Weather Agent
class WeatherResponse(BaseModel):
    temperature: float
    condition: str

def weather_tool(city: str):
    """
    Returns the weather for a given city.

    Args:
      city (str): The name of the city to get the weather for.
    """
    # Simulate a weather API call
    return f"{city} is sunny with a temperature of 25°C."

weather_manifest = ToolManifest(
    description="A tool you can call to see what the weather in a specified city"
    parameter
)
WeatherAgent = rt.agent_node(
    name="Weather Agent",
    llm_model=rt.llm.OpenAILLM("gpt-4o"),
    system_message="You are a helpful assistant that answers weather-related questions.",
    tool_nodes=[rt.function_node(weather_tool)],
    schema=WeatherResponse,
    tool_manifest=weather_manifest
)

#Now lets create a hiking planner agent

HikingAgent = rt.agent_node(
    name="Hiking Agent",
    llm_model=rt.llm.OpenAILLM("gpt-4o"),
    system_message="You are a helpful assistant that answers questions about conditions for hiking.",
    tool_nodes=[WeatherAgent],
)
```

## Tool-Calling Agents

Tool-calling agents can invoke one or more tools during a conversation. This allows them to take actions that conventional LLM's cannot.

When making a Tool-Calling Agent you can also specify `max_tool_calls` to have a safety net for your agents calls. If you don't specify `max_tool_calls`, your agent will be able to make as many tool calls as it sees fit.

### Example
```python
import railtracks as rt

# weather_tool_set would be a list of multiple tools
weather_tool_set = [rt.function_node(weather_tool), rt.function_node(another_tool)]

WeatherAgent = rt.agent_node(
    name="Weather Agent",
    llm_model=rt.llm.OpenAILLM("gpt-4o"),
    system_message="You are a helpful assistant that answers weather-related questions.",
    tool_nodes=weather_tool_set,
    max_tool_calls=10
)
```

Additionally, we have an MCP agent if you would like integrate API functionalities as tools your agent can use directly. See [Using MCP](../tools_mcp/mcp/MCP_tools_in_RT.md) for more details.

### Example
```python

import railtracks as rt

notion_agent_class = rt.agent_node(
    name="Notion Agent",
    tool_nodes=notion_mcp_tools,
    llm_model=rt.llm.OpenAILLM("gpt-4o"),
    system_message="You are a helpful assistant that help edit users Notion pages",
)
```


!!! info "Agents as Tools"
    You might have noticed that `agent_node` accepts a parameter called `manifest`. This is used to define the agent's capabilities and how it can be used as a tool by other agents. You can refer to the [Agents as Tools](../tools_mcp/tools/agents_as_tools.md) for more details.

!!! info "Advanced Usage: Shared Context"
    For advanced usage cases that require sharing context (ie variables, paramters, etc) between nodes please refer to [context](../advanced_usage/context.md), for further configurability.