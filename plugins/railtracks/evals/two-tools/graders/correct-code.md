---
type: llm
focus: {source: file, path: main.py}
weight: 2
---
You are reviewing railtracks code against the current API. PASS only if every item holds:
- Each tool is a plain function decorated with `@rt.function_node` (or wrapped with `rt.function_node(fn)`), with type hints on every parameter and the return value, and a docstring describing it and its arguments.
- The agent is created with `rt.agent_node(...)` passing a name, `tool_nodes=[...]` with both tools, `llm=`, and a `system_message`.
- The agent runs through `rt.Flow(name=..., entry_point=<Agent>)` inside an `if __name__ == "__main__":` block, and the answer is printed from `result.content`.
- `import railtracks as rt`, and every `rt.agent_node(...)` call passes `llm=` (e.g. `rt.llm.OpenAILLM("<model>")`).
- Agent variables are PascalCase.
- Agents run through `rt.Flow` (`flow.invoke` / `await flow.ainvoke`) or `await rt.call(...)` inside a node, never `rt.Session()`; agent results are read with `.content`, never `.text` or `.structured`.
- No invented or removed APIs: no `stream=True` on a model, no `guardrails=` argument, no `Guard(...)`, no `rt.interactive`, no `rt.Agent`/`rt.Tool` classes, no `.run()`/`.chat()` on an agent.
Judge only these items. Variable names in them are placeholders, and extra helper functions, safety checks, comments, docstrings, and stylistic choices are fine: never FAIL for something the items don't mention.
FAIL if any item is missing or wrong; name the item.
