# Ingestion

Ingestion is the write path. A loader produces `Document`s, the chunker
splits them, the embedder vectorizes the chunks, and the store persists the
result. `RetrievalRuntime` runs all four stages as an async stream without
buffering the corpus and waiting for a stage to drain before the next one
starts.

This page covers what you need to run that stream safely in production:
streaming events, re-ingest semantics, multi-tenant writes, sanitization,
and the token guard.

For loader-specific details (TextLoader, PDFs, Hugging Face datasets, custom
sources) see the [Ingestion components pages](../components/ingestion/base.md).

---

## `ingest_all`: one-shot summary

The simplest entry point. Drains the stream and returns an `IngestionStats`:

```python
--8<-- "docs/scripts/retrieval/ingestion_example.py:ingest_all"
```

Use `ingest_all` for batch jobs and tests where you only care about the
summary. Use `ingest` (below) anywhere you need to surface progress, react to
failures, or stream events to another system.

---

## Streaming events

`runtime.ingest()` is an async generator. Each yield is a typed event —
match on it to log, retry, or short-circuit:

```python
--8<-- "docs/scripts/retrieval/ingestion_example.py:streaming"
```

| `.ingest(..)` event outputs | Meaning |
|---|---|
| `BatchIngested` | A batch of chunks finished embedding and was written. |
| `EmbeddingFailure` | A batch failed mid-flight. The stream continues; successful batches for the same document are still written. |
| `DocumentFailed` | End-of-document signalling at least one batch in the document failed. |
| `DocumentSkipped` | The document's `source` + `content_hash` matches an existing entry; no embedding call was made. |

Failures are surfaced as events, not raised. This results in bulk re-indexing across thousands of documents not aborting due to one batch failure.

---

## Re-ingest semantics

```python
--8<-- "docs/scripts/retrieval/ingestion_example.py:reingest"
```

Two paths, both safe to re-run on the same loader:

- **Upsert by `Document.id`.** Calling `ingest` with a `Document` whose `id`
  already exists in the store triggers `store.delete_where({"document_id":
  ...})` after the *first successful batch* lands, then writes the new
  chunks. If every batch fails, the delete never fires and the prior version
  is preserved.
- **Skip by `source` + content hash.** The runtime SHA-256s each document's
  content and looks it up via `store.find`. If a row with the same `source`
  and `content_hash` exists, the runtime yields `DocumentSkipped` without
  calling the embedder. This is what makes `ingest()` cheaply idempotent
  against a stable source.

---

## Multi-tenant writes

Pass `StoreScope` per call to allow stores to hold multi-tenants:

```python
--8<-- "docs/scripts/retrieval/ingestion_example.py:scope_on_write"
```

`StoreScope` wraps an open `labels: Mapping[str, Any]` — pick whichever
axes fit your tenancy model. `{"user_id": "alice"}` for SaaS,
`{"organization": "acme", "environment": "prod"}` for B2B, anything else
that makes sense. Each label becomes a mandatory equality filter on every
write and read. One store can back any number of tenants — the cost of
multi-tenancy is the cost of one extra payload field.

Scope is request-level context, not runtime config — that's why it lives
on `ingest()` / `ingest_all()` / `retrieve()` rather than on the
constructor. Single-tenant callers just omit it.

---

## Sanitizing loaders

`SanitizingLoader(inner, sanitizer)` wraps any loader and passes every
`Document` through your `Sanitizer` before it reaches the chunker. The
`Sanitizer` protocol is one method — `.sanitize(document: Document) ->
Document` — sync or async. Use it for PII redaction or any per-document
normalization:

```python
--8<-- "docs/scripts/retrieval/ingestion_example.py:sanitizing"
```

Sanitization runs once per document, not per chunk — content_hash is
computed on the sanitized text, so the skip-by-hash path stays accurate.

---

## Audit hooks

`on_ingest=callback` fires for every event the stream yields. Especially
useful with `ingest_all`, where you never see events directly and the hook
is your only window into per-batch progress. Use it for audit logs,
metrics, or write-ahead logging:

```python
--8<-- "docs/scripts/retrieval/ingestion_example.py:on_ingest_hook"
```

The callback runs inline with the ingest stream. For anything async or
slow (DB writes, HTTP webhooks), wrap the body in `asyncio.create_task(...)`
so the stream keeps moving and errors then surface on the task instead of
bubbling out of the ingest call.

---

## Token guard

Embedding providers reject oversize inputs server-side. `max_tokens` drops
those chunks pre-flight and surfaces them as `EmbeddingFailure` events
instead of provider 400s:

```python
--8<-- "docs/scripts/retrieval/ingestion_example.py:max_tokens"
```

When `max_tokens` is set without a tokenizer, `RetrievalRuntime` wires up
`TiktokenTokenizer` automatically. Override with `tokenizer=...` if you need
a non-OpenAI tokenizer.

**Pick the limit conservatively.** OpenAI's text-embedding-3 family caps at
8191 tokens; setting `max_tokens=8000` leaves headroom for whatever the
provider counts differently than tiktoken.

---

## Related

- **[Retrieval](retrieval.md)** — the read path: `retrieve()`, filters,
  scope overrides, and patterns for wiring retrieval into an agent.
- **[Components → Ingestion](components/ingestion/index.md)** — the
  built-in loaders, the `Document` shape, custom loaders.
- **[Components → Design](components/design.md)** — internals: streaming
  concurrency model, the `Store` protocol, stage contracts.
