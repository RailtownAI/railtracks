---
type: llm
focus: {source: file, path: main.py}
weight: 2
---
You are reviewing railtracks code against the current API. PASS only if every item holds:
- The input guard is a function decorated with `@rt.input_guard` and the output guard with `@rt.output_guard` (or subclasses of the documented guard bases); each takes an `rt.guardrails.LLMGuardrailEvent` and returns `rt.guardrails.GuardrailDecision.allow()` or `.block(reason=...)`.
- Both guards are attached with `model_middleware=[...]` on `rt.agent_node(...)` (or via `rt.couple(..., model_middleware=[...])`), never with `guardrails=` or a `Guard(...)` container.
- Any prebuilt guards are imported from `railtracks.prebuilt.guardrails`, not `railtracks.guardrails.llm`.
- `import railtracks as rt`, and every `rt.agent_node(...)` call passes `llm=` (e.g. `rt.llm.OpenAILLM("<model>")`).
- Agent variables are PascalCase.
- Agents run through `rt.Flow` (`flow.invoke` / `await flow.ainvoke`), `await rt.call(...)` inside a node, or `rt.astream(...)` when streaming, never `rt.Session()`; agent results are read with `.content`, never `.text` or `.structured`.
- No invented or removed APIs: no `stream=True` on a model, no `guardrails=` argument, no `Guard(...)`, no `rt.interactive`, no `rt.Agent`/`rt.Tool` classes, no `.run()`/`.chat()` on an agent.
Judge only these items. Variable names in them are placeholders, and extra helper functions, safety checks, comments, docstrings, and stylistic choices are fine: never FAIL for something the items don't mention.
FAIL if any item is missing or wrong; name the item.
