# Retrieval

Retrieval allows you to provide context to an agent or to do general queries on
a previously ingested knowledge base. After initliazation of your runtime to connect
to the vectorized knowledge base, `runtime.retrieve(...)` will return `RetrievalResult`
which contains a list of `RetrievedChunk`s

---

## Vector search

```python
--8<-- "docs/scripts/retrieval/retrieval_example.py:basic"
```

`RetrievalResult` is `{query, chunks}` where each `RetrievedChunk` carries
a `score` in `[0, 1]`, a 0-indexed `rank`, and the original `Chunk` (content
+ metadata + `document_id`).

The runtime caches the embedder's reported model name on the first
successful ingest. If a later retrieve uses a runtime whose embedder reports
a different model, you get `EmbeddingModelMismatchError` signaling corruption of the vector spaces.

---

## Metadata filters

Any scalar in `Chunk.metadata` is filterable. The runtime also writes two
well-known keys automatically (`source_path` (from `Document.source`) and
`content_hash`) so you can filter by source without setting metadata
yourself:

```python
--8<-- "docs/scripts/retrieval/retrieval_example.py:metadata_filters"
```

!!! warning "Filters are flat equality only"
    Currently we only support `field==value` for filtering. For other common filtering needs (`or`, `is_in`, etc) please open an issue or a PR at https://github.com/RailtownAI/railtracks/issues

---

## Per-call scope

When the same runtime serves multiple users, pass `StoreScope` on each
`retrieve()` (and `ingest()`) call to isolate their results:

```python
--8<-- "docs/scripts/retrieval/retrieval_example.py:scope_override"
```

Scope is enforced at the store layer, not the runtime and even
`VectorStore.nearest_neighbors()` (the lower-level bypass method) honors
it. And unlike metadata filters, scope is stamped onto entries at write time, not just applied at read time.

---

## Audit hook

`on_retrieve=callback` fires synchronously after every `retrieve()` call,
with `(query: str, result: RetrievalResult)`. Use it for query logs,
hit-rate metrics, or feeding queries into an evaluation harness:

```python
--8<-- "docs/scripts/retrieval/retrieval_example.py:on_retrieve_hook"
```

Like `on_ingest`, it runs on the request path. Push to a queue for any
non-trivial work.

---

## Wiring retrieval into an agent

`runtime.retrieve()` is the only primitive and there's no built-in
"RAG mode" you have to opt into. Two patterns cover most uses:

**As a tool the agent calls deliberately.** The agent decides when it
needs context and what to search for. Best when only some turns need
retrieval (general chat with occasional doc lookups), or when you want
the model to refine queries before each search:

```python
--8<-- "docs/scripts/retrieval/retrieval_example.py:as_tool"
```

**As a pre-invoke step that always injects context.** Retrieval runs on
every agent invocation, transparent to the model. Best when the LLM
should ground answers in the corpus on every turn (docs bots, support
assistants):

```python
--8<-- "docs/scripts/retrieval/retrieval_example.py:as_pre_invoke"
```

Neither pattern hides the retrieval call; you control the query, the
`top_k`, the filters, and where the chunks land in the prompt. Swap
embedders, chunkers, or stores by passing a different runtime to the
agent.

!!! warning "`RagConfig` is being deprecated"
    Earlier versions exposed a `RagConfig` shortcut that wired the
    pre-invoke pattern in one line. It's being removed and the patterns
    above are currently the supported way to attach retrieval to an agent going
    forward.

---

## Related

- **[Ingestion](ingestion.md)** — the write path: streaming events,
  re-ingest, multi-tenant writes, sanitization, token guards.
- **[Components → Stores](../components/stores/base.md)** — the `Store`
  protocol, `StoreQuery`, and the low-level `nearest_neighbors` bypass.
- **[Components → Design](../components/design.md)** — embedding-model guard,
  staleness check, what's not in scope yet (boolean filters, hybrid search,
  built-in reranker).
