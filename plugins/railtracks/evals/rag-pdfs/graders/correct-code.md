---
type: llm
focus: {source: file, path: main.py}
weight: 2
---
You are reviewing railtracks code against the current API. PASS only if every item holds:
- Ingestion uses `RetrievalRuntime(chunker=..., embedder=OpenAIEmbedding(...), store=VectorStore(<backend>))` and `await runtime.ingest_all(loader=PyPDFLoader("manuals"))` (a folder path is valid), checking or reporting `documents_failed`.
- The persistent store is `await ChromaBackend.create(collection_name=..., path=...)` (or `PgvectorBackend`), not `InMemoryVectorBackend` and not `ChromaBackend(...)` without initialization.
- Imports come from `railtracks.retrieval`, `railtracks.retrieval.loaders`, `railtracks.retrieval.chunking`, `railtracks.retrieval.embedding`, and `railtracks.retrieval.stores`.
- The search tool is an `@rt.function_node` with type hints and a docstring that calls `await runtime.retrieve(query, top_k=...)` and formats `result.chunks` (`rc.chunk.content`).
- The agent is an `rt.agent_node(...)` with that tool and `llm=`, run through `rt.Flow`, printing `result.content`.
- `import railtracks as rt`, and every `rt.agent_node(...)` call passes `llm=` (e.g. `rt.llm.OpenAILLM("<model>")`).
- Agent variables are PascalCase.
- Agents run through `rt.Flow` (`flow.invoke` / `await flow.ainvoke`), `await rt.call(...)` inside a node, or `rt.astream(...)` when streaming, never `rt.Session()`; agent results are read with `.content`, never `.text` or `.structured`.
- No invented or removed APIs: no `stream=True` on a model, no `guardrails=` argument, no `Guard(...)`, no `rt.interactive`, no `rt.Agent`/`rt.Tool` classes, no `.run()`/`.chat()` on an agent.
Judge only these items. Variable names in them are placeholders, and extra helper functions, safety checks, comments, docstrings, and stylistic choices are fine: never FAIL for something the items don't mention.
FAIL if any item is missing or wrong; name the item.
