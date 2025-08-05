# How to Build Your First Agent

RailTracks allows you to easily create custom agents using the `define_agent` function by configuring a few simple parameters in any combination!

Start by specifying:

- `llm_model`: Choose which LLM the agent will use.
- `system_message`: Define the agent’s behavior. This guides the agent and often improves output quality.  
  *(See also: [Prompt Engineering](https://en.wikipedia.org/wiki/Prompt_engineering))*

Then, configure your agent class by selecting which functionalities to enable:

- `tools`: If you pass this parameter, the agent gains access to the specified [tools](../guides/tools.md). If you don't it will act as a conversational agent instead.
- `schema`: Given a schema, the agents responses will follow that schema. Otherwise it will return output as it sees fit.

Optionally, you can define attributes for using the agent as a tool itself and debugging:

- `agent_name`: The identifier used when referencing the agent while debugging.
- `agent_params`: [Parameters](../tools) required when the agent is called as a tool.
- `agent_doc`: A short explanation of what the agent does — this helps other LLMs decide when and how to use it.


For advanced users you can see [context](../advanced_usage/context.md), for further configurability.

### Example
```python

weather_agent_class = rt.define_agent(
    agent_name="Weather Agent",
    llm_model="gpt-4o",
    system_message="You are a helpful assistant that answers weather-related questions.",
    tools={weather_tool},
    schema=weather_schema,
    agent_params=weather_param,
    agent_doc="This is an agent that will give you the current weather and answer weather related questions you have"    
)
```


---

## Tool-Calling Agents

Tool-calling agents can invoke one or more tools during a conversation. This allows them to take actions that conventional LLM's cannot.

When making a Tool-Calling Agent you can also specify `max_tool_calls` to have a safety net for your agents calls. If you don't specify `max_tool_calls`, your agent will be able to make as many tool calls as it sees fit.

### Example
```python

weather_agent_class = rt.define_agent(
    agent_name="Weather Agent",
    llm_model="gpt-4o",
    system_message="You are a helpful assistant that answers weather-related questions.",
    tools=weather_tool_set,
    maximum_tool_calls=10
)
```

Additionally, we have an MCP agent if you would like integrate API functionalities as tools your agent can use directly. See [Using MCP](../tools_mcp/mcp/MCP_tools_in_RT.md) for more details.

### Example
```python

notion_agent_class = rt.define_agent(
    agent_name="Notion Agent",
    mcp_command: notion_command,
    mcp_args: notion_args,
    mcp_env: notion_env,
    llm_model="gpt-4o",
    system_message="You are a helpful assistant that help edit users Notion pages",
    
)
```

---

## Structured Agents

Structured agents are built to return output that conforms to a consistent schema (Currently we only support Pydantic models). This is especially useful for:

- Parsing responses programmatically
- Integrating with downstream processes
- Enforcing predictable structure for evaluation or validation

Define the schema or expected structure when initializing the agent so the model can reliably adhere to it.

---

<p style="text-align:center;">
  <a href="../tools_mcp/create_your_own" class="md-button" style="margin:3px">Create Your Own Agent</a>
  <a href="../advanced_usage/context" class="md-button" style="margin:3px">Using Context</a>
</p>
