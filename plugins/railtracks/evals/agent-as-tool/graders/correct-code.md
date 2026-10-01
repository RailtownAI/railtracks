---
type: llm
focus: {source: file, path: main.py}
weight: 2
---
You are reviewing railtracks code against the current API. PASS only if every item holds:
- Each sub-agent is an `rt.agent_node(...)` with `manifest=rt.ToolManifest(description=..., parameters=[...])`, where parameters are `Parameter(name=..., description=..., param_type=...)` objects imported from `railtracks.llm`.
- The orchestrator is an `rt.agent_node(...)` whose `tool_nodes` includes both sub-agents (the agent classes themselves).
- `get_forecast` is an `@rt.function_node` with type hints and a docstring.
- It runs through `rt.Flow(..., entry_point=<Orchestrator>)` and prints `result.content`.
- `import railtracks as rt`, and every `rt.agent_node(...)` call passes `llm=` (e.g. `rt.llm.OpenAILLM("<model>")`).
- Agent variables are PascalCase.
- Agents run through `rt.Flow` (`flow.invoke` / `await flow.ainvoke`) or `await rt.call(...)` inside a node, never `rt.Session()`; agent results are read with `.content`, never `.text` or `.structured`.
- No invented or removed APIs: no `stream=True` on a model, no `guardrails=` argument, no `Guard(...)`, no `rt.interactive`, no `rt.Agent`/`rt.Tool` classes, no `.run()`/`.chat()` on an agent.
Judge only these items. Variable names in them are placeholders, and extra helper functions, safety checks, comments, docstrings, and stylistic choices are fine: never FAIL for something the items don't mention.
FAIL if any item is missing or wrong; name the item.
