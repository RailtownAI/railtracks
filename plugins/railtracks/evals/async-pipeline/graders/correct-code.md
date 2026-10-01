---
type: llm
focus: {source: file, path: main.py}
weight: 2
---
You are reviewing railtracks code against the current API. PASS only if every item holds:
- The pipeline is an `async def` decorated with `@rt.function_node` (or otherwise usable as a Flow entry point) that runs `await rt.call(SummaryAgent, ...)` then `await rt.call(TranslatorAgent, <step1>.content)`, passing the first result's `.content` (not the response object) to the second agent.
- The flow is `rt.Flow(..., entry_point=<pipeline>)`, run with `await flow.ainvoke(...)` inside `async def main()`, started with `asyncio.run(main())`.
- `import railtracks as rt`, and every `rt.agent_node(...)` call passes `llm=` (e.g. `rt.llm.OpenAILLM("<model>")`).
- Agent variables are PascalCase.
- Agents run through `rt.Flow` (`flow.invoke` / `await flow.ainvoke`), `await rt.call(...)` inside a node, or `rt.astream(...)` when streaming, never `rt.Session()`; agent results are read with `.content`, never `.text` or `.structured`.
- No invented or removed APIs: no `stream=True` on a model, no `guardrails=` argument, no `Guard(...)`, no `rt.interactive`, no `rt.Agent`/`rt.Tool` classes, no `.run()`/`.chat()` on an agent.
Judge only these items. Variable names in them are placeholders, and extra helper functions, safety checks, comments, docstrings, and stylistic choices are fine: never FAIL for something the items don't mention.
FAIL if any item is missing or wrong; name the item.
