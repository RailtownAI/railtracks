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
--8<-- "docs/scripts/byfa.py:imports"

--8<-- "docs/scripts/byfa.py:weather_response"

--8<-- "docs/scripts/byfa.py:first_agent"
```


## Tool-Calling Agents

Tool-calling agents can invoke one or more tools during a conversation. This allows them to take actions that conventional LLM's cannot.

When making a Tool-Calling Agent you can also specify `max_tool_calls` to have a safety net for your agents calls. If you don't specify `max_tool_calls`, your agent will be able to make as many tool calls as it sees fit.

### Example


Additionally, we have an MCP agent if you would like integrate API functionalities as tools your agent can use directly. See [Using MCP](../tools_mcp/mcp/MCP_tools_in_RT.md) for more details.

### Example
```python

--8<-- "docs/scripts/byfa.py:1:2"

--8<-- "docs/scripts/byfa.py:notion_agent"

```


!!! info "Agents as Tools"
    You might have noticed that `agent_node` accepts a parameter called `manifest`. This is used to define the agent's capabilities and how it can be used as a tool by other agents. You can refer to the [Agents as Tools](../tools_mcp/tools/agents_as_tools.md) for more details.

!!! info "Advanced Usage: Shared Context"
    For advanced usage cases that require sharing context (ie variables, paramters, etc) between nodes please refer to [context](../advanced_usage/context.md), for further configurability.
    