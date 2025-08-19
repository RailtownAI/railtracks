# How to Build Your First Agent

RailTracks makes it easy to create custom agents using the **`agent_node`** function. You can configure your agent's capabilities by setting a few key parameters.

## Required Parameters

First, specify these essential components:

- **`llm_model`**: The LLM that powers your agent (e.g., OpenAI GPT, Claude, etc.)
- **`system_message`**: Instructions that define your agent's behavior and personality

Then, enhance your agent with additional capabilities:

- **`tool_nodes`**: Provide your agent with [tools](../tools_mcp/tools/tools.md) to interact with external systems. Without tools, your agent will function as a conversational assistant.
- **`schema`**: Define a structured output format using Pydantic models. Without a schema, the agent will respond in natural language.

!!! info "Agent Types"
    Based on the provided values to the above parameters, your agent's capabilities can range from simple conversational agents to more complex tool-using agents capable of extracting structured data out of unstructured text.

    ??? tip "Structured Agents"
        RailTracks supports structured agents that return output conforming to a specified schema. This is useful for ensuring consistent and predictable responses, especially when integrating with other systems or processes. This can be achieved by passing a Pydantic model to the **`schema`** parameter.

    ??? tip "Tool-Calling Agents"
        Tool-calling agents can invoke one or more tools during a conversation. This allows them to take actions that conventional LLM's cannot. As seen in the example below, your agent becomes capable of invoking the different tools passed to the **`tool_nodes`** parameter. Please refer to [RailTracks Tools](../tools_mcp/tools_mcp.md) for further details

```python
--8<-- "docs/scripts/first_agent.py:imports"

--8<-- "docs/scripts/first_agent.py:weather_response"

--8<-- "docs/scripts/first_agent.py:first_agent"
```

!!! tip "Number of tool calls"
    When making a Tool-Calling Agent you can also specify **`max_tool_calls`** to have a safety net for your agents calls. If you don't specify **`max_tool_calls`**, your agent will be able to make as many tool calls as it sees fit.

!!! warning "Number of tools"
    The maximum number of tools an agent can call is limited by the LLM you are using both in terms of the number of tools supported and the context length which needs to incorporate the information about the tools.

??? info "MCP Tools"
    We have an MCP agent if you would like integrate API functionalities as tools your agent can use directly. See [Using MCP](../tools_mcp/mcp/MCP_tools_in_RT.md) for more details.

??? info "Agents as Tools"
    You might have noticed that **`agent_node`** accepts a parameter called **`manifest`**. This is used to define the agent's capabilities and how it can be used as a tool by other agents. You can refer to the [Agents as Tools](../tools_mcp/tools/agents_as_tools.md) for more details.

??? info "Advanced Usage: Shared Context"
    For advanced usage cases that require sharing context (ie variables, paramters, etc) between nodes please refer to [context](../advanced_usage/context.md), for further configurability.
    