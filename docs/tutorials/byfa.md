# Build Your First Agent

In the [quickstart](../quickstart/quickstart.md), you ran a ready-made agent. Now let’s build your own step by step, starting from the simplest form and gradually adding more abilities.

## Simple LLM Agent
Start with minimal ingredients: a model + a system message

```python
--8<-- "docs/scripts/first_agent.py:simple_llm"
```

??? question "Supported LLMs"
    Check out our full list of [supported providers](../llm_support/providers.md)

## Adding Tool Calling
What if your agent needs real-world data? You will need to give it [tools](../tools_mcp/tools/tools.md). This allows your agent to go beyond static responses and actually interact with the real world.

??? tip "Creating a Tool"
    All you need is a Python function with docstring and the `rt.function_node` decorator
    ```python 
    --8<-- "docs/scripts/first_agent.py:general_tool"
    ```
    [Learn more about tools](../tools_mcp/tools/tools.md)



```python 
--8<-- "docs/scripts/first_agent.py:weather_tool"

--8<-- "docs/scripts/first_agent.py:first_agent_tools"
```

???+ note "Using MCP servers"
    MCP servers can be used as tools in the RT framework. 

    To connect to an MCP, please refer to our [guide](../tools_mcp/mcp/mcp.md)

## Adding a Structured Output
Now that you've seen how to add tools. Let's look at your agent can respond with reliable typed outputs. Schemas give you reliable, machine-checked outputs you can safely consume in code, rather than brittle strings.

??? tip "Defining a Schema"
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
Often you will want the best of both worlds, an agent capable of both tool calling and responding in a structured format. 

```python 
--8<-- "docs/scripts/first_agent.py:first_agent_all"
```



---
# Running Agents
Congratulations, you’ve now built agents that call tools, return structured outputs, and even combine both. Next, let’s actually run them and see them in action -> [Running your First Agent](ryfa.md).
