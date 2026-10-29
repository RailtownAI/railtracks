We support using agents as tools in the following three ways:

## 1. Pass the Agent Directly

Any agent with a `system_message` can go straight into another agent's `tool_nodes`. Railtracks describes it to the calling agent using its name and system message, and the calling agent hands it a single string argument, `request`, which the agent receives as its user message.

```python
import railtracks as rt

WeatherAgent = rt.agent_node(
    "Weather Agent",
    llm=rt.llm.OpenAILLM("gpt-6-luna"),
    system_message="You find the current weather and forecast for a city.",
)

Assistant = rt.agent_node(
    "Assistant",
    llm=rt.llm.OpenAILLM("gpt-6-luna"),
    system_message="You are a general assistant.",
    tool_nodes=[WeatherAgent],
)
```

Here the calling agent sees a tool named `Weather_Agent` with this description:

```text
Hands a task to the sub-agent "Weather Agent" and returns its final reply. The sub-agent follows these instructions:
You find the current weather and forecast for a city.
```

What to know about the generated tool

- The whole system message goes into the calling agent's tool list. The calling agent can read it, and it is sent with every model call the calling agent makes. Write a manifest (below) if you want a shorter description, or one that doesn't reveal the prompt.
- The description is built once, when the calling agent is created, and placeholders in it are never filled. With a system message like `"You help {customer_name}."`, the sub-agent still gets the filled value when it uses [`ContextInjection`](https://docs.railtracks.org/documentation/agent_design/middleware/prebuilt/list/context_injection/index.md), but the calling agent sees `{customer_name}` as written, because `ContextInjection` fills messages, not tool descriptions. Write a manifest if the description must not contain placeholders.
- An agent with neither a system message nor a manifest raises `NodeCreationError` when you pass it to `tool_nodes`.

## 2. Tool Manifest

A **tool manifest** is the description an agent carries of how other agents may call it: a description of what it does and the parameters it expects. Passing `manifest=` at agent definition time sets these yourself, replacing the generated description and parameters.

```python
ManifestWeatherAgent = rt.agent_node(
    "Weather Agent",
    llm=rt.llm.OpenAILLM("gpt-6-luna"),
    system_message="You find the current weather and forecast for a city.",
    manifest=rt.ToolManifest(
        description="Gets the current weather and forecast for a city.",
        parameters=[
            rt.llm.Parameter(
                name="city",
                description="The city to look up.",
                param_type="string",
            ),
        ],
    ),
)
```

A manifest without `parameters` keeps your description and takes the `request` argument described above. A manifest with a blank description raises `NodeCreationError`.

## 3. Python Function

By using a python function to call your agent, you can have the flexibility of your agent being invoked in different ways in different contexts. You will then simply [pass this function as a tool](https://docs.railtracks.org/documentation/agent_design/tools/function_tools/index.md) to your Orchestrator.

```python
@rt.function_node
async def weather_report(city: str, units: str) -> str:
    """Get a short weather report for a city.

    Args:
        city: The city to report on.
        units: Either "metric" or "imperial".
    """
    response = await rt.call(WeatherAgent, f"Weather in {city}, in {units} units.")
    return response.content


FunctionAssistant = rt.agent_node(
    "Assistant",
    llm=rt.llm.OpenAILLM("gpt-6-luna"),
    system_message="You are a general assistant.",
    tool_nodes=[weather_report],
)
```

You can refer to [API Reference](https://docs.railtracks.org/api_reference/railtracks.html) for more information. Or take a look at the [Agents as Tools](https://docs.railtracks.org/tutorials/walkthroughs/agents_as_tools/index.md) walkthrough.
