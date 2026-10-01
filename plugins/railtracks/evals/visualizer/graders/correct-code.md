---
type: llm
focus: trace
weight: 2
---
You are reviewing railtracks code against the current API. PASS only if every item holds:
- Tells the user to install the visualizer extra (`pip install 'railtracks[visual]'`), run `railtracks init`, and start it with `railtracks viz --beta` from the project root.
- Says runs are recorded automatically, with no extra code needed in the agent, or at least adds none that doesn't exist (no invented `rt.enable_visualizer`, `rt.set_config(...)` or similar).
- `import railtracks as rt`, and every `rt.agent_node(...)` call passes `llm=` (e.g. `rt.llm.OpenAILLM("<model>")`).
- Agent variables are PascalCase.
- Agents run through `rt.Flow` (`flow.invoke` / `await flow.ainvoke`) or `await rt.call(...)` inside a node, never `rt.Session()`; agent results are read with `.content`, never `.text` or `.structured`.
- No invented or removed APIs: no `stream=True` on a model, no `guardrails=` argument, no `Guard(...)`, no `rt.interactive`, no `rt.Agent`/`rt.Tool` classes, no `.run()`/`.chat()` on an agent.
Judge only these items. Variable names in them are placeholders, and extra helper functions, safety checks, comments, docstrings, and stylistic choices are fine: never FAIL for something the items don't mention.
FAIL if any item is missing or wrong; name the item.
