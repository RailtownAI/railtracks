# How to Build Your First Agent

RailTracks allows you to easily create custom agents using the `agent_node` function by configuring a few simple parameters in any combination!

Start by specifying:

- `llm_model`: Choose which LLM the agent will use.
- `system_message`: Define the agent’s behavior. This guides the agent and often improves output quality.  

Then, configure your agent class by selecting which functionalities to enable:

- `tool_nodes`: If you pass this parameter, the agent gains access to the specified [tools](../tools_mcp/tools/tools.md). If you don't it will act as a conversational agent instead.
- `schema`: Given a schema, the agents responses will follow that schema. Otherwise it will return output as it sees fit.

!!! info "Structured Agents"
    RailTracks supports structured agents that return output conforming to a specified schema. This is useful for ensuring consistent and predictable responses, especially when integrating with other systems or processes. This can be achieved by passing a Pydantic model to the `schema` parameter.


### Example
```python
import railtracks as rt
from pydantic import BaseModel

class WeatherResponse(BaseModel):
    temperature: float
    condition: str

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
    llm_model=rt.llm.OpenAILLM("gpt-4o"),
    system_message="You are a helpful assistant that answers weather-related questions.",
    tool_nodes=[rt.function_node(weather_tool)],
    schema=WeatherResponse,
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