# Retrieval-Augmented Generation (RAG)

`railtracks.retrieval` is the single module for everything RAG. One class —
`RetrievalRuntime` — wires together the four stages: **load → chunk → embed → store**.

Pass the same runtime to `RagConfig` to attach it to an agent, or call
`runtime.retrieve()` directly when you want raw control.

!!! info "Migrated from older modules"
    The previous `railtracks.rag` and `railtracks.vector_stores` modules have been
    removed. All functionality lives under `railtracks.retrieval`.

---

## Minimal pipeline

```python
--8<-- "docs/scripts/retrieval_example.py:minimal"
```

Three knobs decide the shape of a runtime: **chunker**, **embedder**, **store**.
Everything else (scope, batch size, hooks, token limits) has sensible defaults
and is opt-in.

---

## Streaming ingestion

`runtime.ingest()` yields per-batch events as documents flow through the
pipeline. Use it when you want to surface progress to a user or react to
failures mid-flight:

```python
--8<-- "docs/scripts/retrieval_example.py:streaming"
```

Event types:

| Event | When |
|---|---|
| `BatchIngested` | A batch of chunks finished embedding and was written |
| `EmbeddingFailure` | A batch failed; successful batches for the same doc are still written |
| `DocumentFailed` | End-of-document signal when *any* batch in the doc failed |
| `DocumentSkipped` | Document has the same `source` + `content_hash` as an existing entry (staleness check) |

For one-shot ingestion that returns a summary, use `runtime.ingest_all(loader)`
which drains the stream and returns an `IngestionStats`.

---

## Re-ingest semantics

Ingesting a document with a `Document.id` that already exists in the store
upserts it: the runtime issues `store.delete_where({"document_id": ...})`
before the first chunk lands, then writes the new chunks. If *every* batch
for a re-ingest fails, the prior version is preserved (the delete only fires
once at least one batch succeeds).

Ingesting a document with the same `source` and identical content is a no-op:
the runtime hashes the content (SHA-256), looks it up via `store.find`, and
yields `DocumentSkipped` without calling the embedder.

---

## Multi-tenant retrieval

Hand a `StoreScope` to the runtime. Every write carries the scope; every
read filters on it:

```python
--8<-- "docs/scripts/retrieval_example.py:multitenant"
```

`StoreScope` is just `(user_id, agent_id, session_id, run_id)` — any non-`None`
field becomes a mandatory equality filter. A scope can also be passed
per-call to `runtime.retrieve(scope=...)` to override the runtime default.

---

## Plugging into an agent

```python
--8<-- "docs/scripts/retrieval_example.py:agent"
```

`RagConfig(runtime, top_k)` registers a pre-invoke hook that retrieves
relevant chunks based on the message history and injects them into the
prompt. The agent itself stays untouched.

---

## Metadata filtering

Any scalar value in `Chunk.metadata` is filterable. The runtime also writes
two well-known keys automatically: `source_path` (from `Document.source`)
and `content_hash`. Combine them in `metadata_filters`:

```python
--8<-- "docs/scripts/retrieval_example.py:filters"
```

Filters are flat equality (`field == value`). Boolean combinators are not
currently part of the canonical surface; for richer filters, post-filter
results in Python or open an issue.

---

## Production safety hooks

`RetrievalRuntime` exposes three opt-in safety features:

| Parameter | Purpose |
|---|---|
| `on_ingest=callback` | Synchronous callback fired with each `IngestionEvent`. Use for audit logging. |
| `on_retrieve=callback` | Synchronous callback fired with `(query, RetrievalResult)`. |
| `max_tokens=N` | Drops chunks above the token limit before sending to the provider; oversize chunks become `EmbeddingFailure`s instead of API errors. Requires a `Tokenizer` (defaults to `TiktokenTokenizer` when `max_tokens` is set). |

For PII redaction or any per-document sanitization, wrap a loader in
`SanitizingLoader(inner, sanitizer)` — see `retrieval/loaders/sanitizing.py`.

---

## Related pages

- **[Components → Design](components/design.md)** — what each stage looks like.
- **[Components → Stores → Overview](components/stores/overview.md)** — the `Store` protocol and `VectorStore` backends.
- **[Components → Ingestion → Overview](components/ingestion/overview.md)** — loaders and the `Document` model.
- **[Components → Chunking → Methods](components/chunking/methods.md)** — chunking strategies.
- **[Components → Embeddings → Overview](embeddings/overview.md)** — embedder choices.
