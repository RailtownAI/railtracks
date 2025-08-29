# How to Build Your First Agent

RailTracks makes it easy to create custom agents using the **`agent_node`**. Through this one function you can create any agent you want. 

## Simple LLM Agent
You will need to the provide the following parameters:

- **`llm`**: The LLM that powers your agent (e.g., OpenAI GPT, Claude, see [full list](../llm_support/providers.md))
- **`system_message`**: Instructions that define your agent's instructions/behavior

```python
--8<-- "docs/scripts/first_agent.py:simple_llm"
```

## Adding Tool Calling
An LLM without [tools](../tools_mcp/tools/tools.md) is not very special. Giving to access to tools unlocks the possibilities with LLMs. 
To use tools you will need to fill:

- **`tool_nodes`**: The python function that your `agent` can access. 

??? tip "Creating a Tool"
    All you need a is a python function with docstring and the `rt.function_node` decorator
    ```python 
    --8<-- "docs/scripts/first_agent.py:general_tool"
    ```
    [Learn more about tools](../tools_mcp/tools/tools.md)



```python 
--8<-- "docs/scripts/first_agent.py:weather_tool"

--8<-- "docs/scripts/first_agent.py:first_agent_tools"
```

## Adding a Structured Output
Often it is nice to force the LLM to output in a specific schema. 
To force the LLM to respond in a structure format, use the following paramater:

- **`output_schema`**: Define a structured output format using Pydantic models. 

??? tip "Creating a Schema"
    We use the Pydantic library to define structured data models.
    ```python
    --8<-- "docs/scripts/first_agent.py:general_structured"
    ```
    Visit the [pydantic docs](https://docs.pydantic.dev/latest/) to learn about what you can do with `BaseModel`'s

```python 
--8<-- "docs/scripts/first_agent.py:weather_response"

--8<-- "docs/scripts/first_agent.py:first_agent_model"
```

## Structured + Tool Calling
Railtracks provides an additional functionality for a model which can tool call and will return a structured output. To accomplish this, you should provide both `output_schema` and `tool_nodes`. 

```python 
--8<-- "docs/scripts/first_agent.py:first_agent_all"
```

## Connecting to MCP 
To connect to MCP, please refer to our [guide](../tools_mcp/mcp/mcp.md)

---
# Running Agents
Now that you have created your agents, you are ready to run them. Vist [Running your First Agent](ryfa.md) 
