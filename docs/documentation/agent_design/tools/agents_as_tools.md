We support using agents as tools in the following three ways:

## 1. Pass the Agent Directly
Any agent with a `system_message` can go straight into another agent's `tool_nodes`. Railtracks describes it to the calling agent using its name and system message, and the calling agent hands it a single string argument, `request`, which the agent receives as its user message.
```python
--8<-- "docs/scripts/documentation/agent_tool_options.py:direct"
```

Here the calling agent sees a tool named `Weather_Agent` with this description:

```text
Hands a task to the sub-agent "Weather Agent" and returns its final reply. The sub-agent follows these instructions:
You find the current weather and forecast for a city.
```

!!! note "What to know about the generated tool"
    - The whole system message goes into the calling agent's tool list. The calling agent can read it, and it is sent with every model call the calling agent makes. Write a manifest (below) if you want a shorter description, or one that doesn't reveal the prompt.
    - The description is built once, when the calling agent is created, and placeholders in it are never filled. With a system message like `"You help {customer_name}."`, the sub-agent still gets the filled value when it uses [`ContextInjection`](../middleware/prebuilt/list/context_injection.md), but the calling agent sees `{customer_name}` as written, because `ContextInjection` fills messages, not tool descriptions. Write a manifest if the description must not contain placeholders.
    - An agent with neither a system message nor a manifest raises `NodeCreationError` when you pass it to `tool_nodes`.

## 2. Agent Manifest
In this way, at agent definition time, you also define how this agent can be used by other agents. The manifest replaces the generated description and parameters.
```python
--8<-- "docs/scripts/documentation/agent_tool_options.py:manifest"
```

A manifest without `parameters` keeps your description and takes the `request` argument described above. A manifest with a blank description raises `NodeCreationError`.

## 3. Python Function
By using a python function to call your agent, you can have the flexibility of your agent being invoked in different ways in different contexts. You will then simply [pass this function as a tool](function_tools.md) to your Orchestrator.
```python
--8<-- "docs/scripts/documentation/agent_tool_options.py:function"
```

You can refer to [API Reference](../../../api_reference/railtracks.html) for more information. Or take a look at our [Agents as Tools tutorial](../../../tutorials/walkthroughs/agents_as_tools.md).
