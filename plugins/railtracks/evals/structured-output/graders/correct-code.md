---
type: llm
focus: {source: file, path: main.py}
weight: 2
---
You are reviewing railtracks code against the current API. PASS only if every item holds:
- The output is a Pydantic `BaseModel` subclass with fields for the name, email, and phone (any field names; optional fields are fine).
- The agent is created with `rt.agent_node(..., output_schema=<Model>, llm=...)` and does NOT also pass `tool_nodes` (passing both raises NodeCreationError).
- The agent is run through `rt.Flow(..., entry_point=<Agent>)` and `flow.invoke(...)` (or `await flow.ainvoke(...)`), and the fields are read from `result.content`, which is an instance of the model (read directly, or after assigning it to a variable).
- `import railtracks as rt`, and every `rt.agent_node(...)` call passes `llm=` (e.g. `rt.llm.OpenAILLM("<model>")`).
- Agent variables are PascalCase.
- Agents run through `rt.Flow` (`flow.invoke` / `await flow.ainvoke`) or `await rt.call(...)` inside a node, never `rt.Session()`; agent results are read with `.content`, never `.text` or `.structured`.
- No invented or removed APIs: no `stream=True` on a model, no `guardrails=` argument, no `Guard(...)`, no `rt.interactive`, no `rt.Agent`/`rt.Tool` classes, no `.run()`/`.chat()` on an agent.
Judge only these items. Variable names in them are placeholders, and extra helper functions, safety checks, comments, docstrings, and stylistic choices are fine: never FAIL for something the items don't mention.
FAIL if any item is missing or wrong; name the item.
