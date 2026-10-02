# Railtracks

This project uses [Railtracks](https://docs.railtracks.org/) (`import railtracks as rt`), a Python framework for building agents. Follow these rules when writing Railtracks code; the API differs from what you may remember.

## Core patterns

```python
import railtracks as rt
from pydantic import BaseModel


@rt.function_node
def get_weather(city: str) -> str:
    """Look up the current weather for a city.

    Args:
        city: The city to look up.
    Returns:
        A short weather summary.
    """
    return f"Sunny in {city}"


llm = rt.llm.AnthropicLLM("claude-sonnet-5-5")  # or rt.llm.OpenAILLM, rt.llm.GeminiLLM, ...

# agent_node returns a class: give it a PascalCase name.
WeatherAgent = rt.agent_node(
    "Weather Agent",
    llm=llm,  # required
    tool_nodes=[get_weather],
    system_message="You answer weather questions.",
)


class Report(BaseModel):
    city: str
    summary: str


ReportAgent = rt.agent_node("Report Agent", llm=llm, output_schema=Report)

flow = rt.Flow(name="Weather", entry_point=WeatherAgent)

if __name__ == "__main__":
    result = flow.invoke("What's the weather in Paris?")  # await flow.ainvoke(...) in async code
    print(result.content)  # a str here; a Report instance for ReportAgent
```

- **Tools** are functions decorated with `@rt.function_node`. Type hints become the parameter schema and the docstring becomes the description the LLM sees, so write both.
- **Agents** come from `rt.agent_node(name, llm=..., tool_nodes=[...] or output_schema=Model, system_message=...)`. Pass `llm=` every time; it's required. Pass at most one of `tool_nodes` and `output_schema`.
- **Run** an agent through `rt.Flow(name=..., entry_point=Agent)` with `flow.invoke(...)` or `await flow.ainvoke(...)`. For multi-step work, make the entry point an `async` `@rt.function_node` that calls agents with `await rt.call(Agent, ...)`. Give each agent one entry point: a `Flow`, or `rt.call` inside another node.
- **Results** are read with `result.content` (a `str`, or your `output_schema` instance) and `result.message_history` (the full conversation). When the agent was given an `output_schema`, `result.structured` also returns that instance; otherwise `result.text` also returns the `str`.
- **Streaming** is `rt.astream(Agent, user_input=...)`, async only: `async for chunk in stream`, then `stream.result`.
- **Agent as a tool**: pass `manifest=rt.ToolManifest(description=..., parameters=[...])` to `agent_node`, then list that agent in another agent's `tool_nodes`.
- **Middleware**: `middleware=[...]` wraps the whole node; `model_middleware=[...]` wraps each LLM call. The first entry is outermost. Use `@rt.wrap_node`, `@rt.wrap_llm`, `@rt.pre_llm`, `@rt.post_llm`, `@rt.post_node`, and `@rt.input_guard` / `@rt.output_guard` in `model_middleware=[...]` for guardrails. Prebuilt guards come from `railtracks.prebuilt.guardrails`; for example, `model_middleware=[BlockTextInputGuard(pattern=r"(?i)password")]` blocks input that matches a regex.

## More help

- Docs: https://docs.railtracks.org/ (an index for LLMs is at https://docs.railtracks.org/llms.txt, the full text at https://docs.railtracks.org/llms-full.txt).
- For multi-step work such as RAG pipelines or middleware, the user can install the bundled skills with `railtracks add claude:all` (or `codex:all`, `copilot:all`, `cursor:all`).

Written by railtracks {railtracks_version}; rerun `railtracks agents-md` after upgrading.
