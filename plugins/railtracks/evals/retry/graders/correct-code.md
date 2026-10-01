---
type: llm
focus: {source: file, path: main.py}
weight: 2
---
You are reviewing railtracks code against the current API. PASS only if every item holds:
- Retries use `Retry(max_tries=...)` from `railtracks.prebuilt.middleware` (or `rt.prebuilt.middleware.Retry`).
- `Retry` is attached with `model_middleware=[...]` so only the raw LLM call is retried, NOT with `middleware=[...]` on the agent (which would re-run the whole node, including `send_email`).
- `send_email` is an `@rt.function_node` with type hints and a docstring.
- `import railtracks as rt`, and every `rt.agent_node(...)` call passes `llm=` (e.g. `rt.llm.OpenAILLM("<model>")`).
- Agent variables are PascalCase.
- Agents run through `rt.Flow` (`flow.invoke` / `await flow.ainvoke`) or `await rt.call(...)` inside a node, never `rt.Session()`; agent results are read with `.content`, never `.text` or `.structured`.
- No invented or removed APIs: no `stream=True` on a model, no `guardrails=` argument, no `Guard(...)`, no `rt.interactive`, no `rt.Agent`/`rt.Tool` classes, no `.run()`/`.chat()` on an agent.
Judge only these items. Variable names in them are placeholders, and extra helper functions, safety checks, comments, docstrings, and stylistic choices are fine: never FAIL for something the items don't mention.
FAIL if any item is missing or wrong; name the item.
