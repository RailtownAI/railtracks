# Ingestion

Ingestion is the write path. A loader produces `Document`s, the chunker splits them, the embedder vectorizes the chunks, and the store persists the result. `RetrievalRuntime` runs all four stages as an async stream without buffering the corpus and waiting for a stage to drain before the next one starts.

This page covers what you need to run that stream safely in production: streaming events, re-ingest semantics, multi-tenant writes, sanitization, and the token guard.

For loader-specific details (TextLoader, PDFs, Hugging Face datasets, custom sources) see the [Ingestion components pages](https://docs.railtracks.org/retrieval/components/ingestion/base/index.md).

______________________________________________________________________

## `ingest_all`: one-shot summary

The simplest entry point. Drains the stream and returns an `IngestionStats`:

```python
async def main(runtime: RetrievalRuntime):
    # Drains the stream and returns an IngestionStats summary.
    stats = await runtime.ingest_all(TextLoader("./docs"))
    print(
        f"loaded={stats.documents_loaded} "
        f"chunks={stats.chunks_embedded} "
        f"skipped={stats.documents_skipped}"
    )
```

Use `ingest_all` for batch jobs and tests where you only care about the summary. Use `ingest` (below) anywhere you need to surface progress, react to failures, or stream events to another system.

If a JSON or Hugging Face content field contains a dictionary or list, normalize it at the loader boundary before chunking and embedding. The built-in [`JsonExtractor` and `ProseExtractor`](https://docs.railtracks.org/retrieval/components/ingestion/methods/#structured-content-extractors) preserve structure as valid JSON or labelled prose while leaving metadata raw.

______________________________________________________________________

## Streaming events

`runtime.ingest()` is an async generator. Each yield is a typed event - match on it to log, retry, or short-circuit:

```python
from railtracks.retrieval import (
    BatchIngested,
    DocumentFailed,
    DocumentSkipped,
    EmbeddingFailure,
    RetrievalRuntime,
)


async def stream(runtime: RetrievalRuntime, loader):
    async for event in runtime.ingest(loader):
        match event:
            case BatchIngested(document_id=did, embedded_chunks=ch, batch_index=i):
                print(f"  + doc={did} batch={i} chunks={len(ch)}")
            case EmbeddingFailure(errors=errs):
                print(f"  ! batch failed: {errs[0]}")
            case DocumentFailed(document_id=did):
                print(f"  ! doc {did} ended with failures")
            case DocumentSkipped(source=src):
                print(f"  ~ skipped (unchanged): {src}")
```

| `.ingest(..)` event outputs | Meaning                                                                                                      |
| --------------------------- | ------------------------------------------------------------------------------------------------------------ |
| `BatchIngested`             | A batch of chunks finished embedding and was written.                                                        |
| `EmbeddingFailure`          | A batch failed mid-flight. The stream continues; successful batches for the same document are still written. |
| `DocumentFailed`            | End-of-document signalling at least one batch in the document failed.                                        |
| `DocumentSkipped`           | The document's `source` + `content_hash` matches an existing entry; no embedding call was made.              |

Failures are surfaced as events, not raised. This results in bulk re-indexing across thousands of documents not aborting due to one batch failure.

______________________________________________________________________

## Re-ingest semantics

```python
from railtracks.retrieval import Document, DocumentType

class SampleLoader(BaseDocumentLoader):

    doc = Document(content="...", type=DocumentType.TEXT, source="handbook.md")
    async def astream(self):
        yield self.doc

async def reingest(runtime: RetrievalRuntime):
    # Same Document.id → upsert. The runtime clears prior chunks for this
    # document after the first batch succeeds, then writes the new ones.
    # A full embedding failure leaves the prior version intact.
    await runtime.ingest_all(loader=SampleLoader())

    # Same source + identical content → skipped via SHA-256 content_hash lookup.
    # ingest() yields DocumentSkipped without calling the embedder.
    await runtime.ingest_all(loader=SampleLoader())
```

Two paths, both safe to re-run on the same loader:

- **Upsert by `Document.id`.** Calling `ingest` with a `Document` whose `id` already exists in the store triggers `store.delete_where({"document_id": ...})` after the *first successful batch* lands, then writes the new chunks. If every batch fails, the delete never fires and the prior version is preserved.
- **Skip by `source` + content hash.** The runtime SHA-256s each document's content and looks it up via `store.find`. If a row with the same `source` and `content_hash` exists, the runtime yields `DocumentSkipped` without calling the embedder. This is what makes `ingest()` cheaply idempotent against a stable source.

______________________________________________________________________

## Multi-tenant writes

Pass `StoreScope` per call to allow stores to hold multi-tenants:

```python
from railtracks.retrieval.stores import StoreScope  # noqa: E402


async def multitenant_write():
    # One runtime, one store, one set of infrastructure. Scope is a
    # per-call parameter — not a constructor argument — because it's
    # request-level context, not runtime config.
    runtime = RetrievalRuntime(
        chunker=RecursiveCharacterChunker(chunk_size=800),
        embedder=OpenAIEmbedding(),
        store=VectorStore(InMemoryVectorBackend()),
    )

    await runtime.ingest_all(
        TextLoader("./alice_docs"), scope=StoreScope(labels={"user_id": "alice"})
    )
    await runtime.ingest_all(
        TextLoader("./bob_docs"), scope=StoreScope(labels={"user_id": "bob"})
    )

    # Reads pass scope the same way; nothing crosses tenants.
    await runtime.retrieve("favorite color", scope=StoreScope(labels={"user_id": "alice"}))
```

`StoreScope` wraps an open `labels: Mapping[str, Any]`. Pick whichever axes fit your tenancy model. `{"user_id": "alice"}` for SaaS, `{"organization": "acme", "environment": "prod"}` for B2B, anything else that makes sense. Each label becomes a mandatory equality filter on every write and read. One store can back any number of tenants; the cost of multi-tenancy is the cost of one extra payload field.

Scope is request-level context, not runtime config; that's why it lives on `ingest()` / `ingest_all()` / `retrieve()` rather than on the constructor. Single-tenant callers just omit it.

______________________________________________________________________

## Sanitizing loaders

`SanitizingLoader(inner, sanitizer)` wraps any loader and passes every `Document` through your `Sanitizer` before it reaches the chunker. The `Sanitizer` protocol is one method: `.sanitize(document: Document) -> Document` (sync or async). Use it for PII redaction or any per-document normalization:

```python
import re

from railtracks.retrieval.loaders import SanitizingLoader, TextLoader


class EmailRedactor:
    """Implements the Sanitizer protocol: .sanitize(Document) -> Document.
    Stateful by design — real redactors hold compiled regexes, denylists,
    or an async client to a DLP service."""

    EMAIL = re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b")

    def sanitize(self, document: Document) -> Document:
        document.content = self.EMAIL.sub("[REDACTED]", document.content)
        return document


# Wrap any loader. Sanitizer runs once per Document, before chunking.
loader: BaseDocumentLoader = SanitizingLoader(TextLoader("./hr_docs"), sanitizer=EmailRedactor())
```

Sanitization runs once per document, not per chunk; content_hash is computed on the sanitized text, so the skip-by-hash path stays accurate.

______________________________________________________________________

## Audit hooks

`on_ingest=callback` fires for every event the stream yields. Especially useful with `ingest_all`, where you never see events directly and the hook is your only window into per-batch progress. Use it for audit logs, metrics, or write-ahead logging:

```python
import asyncio


def audit(event):
    # Sync hook — runs inline with the ingest stream. Keep it cheap:
    # logging, in-process counters, metrics .inc() calls.
    print(f"[audit] {type(event).__name__}: {event}")


def audit_async(event):
    # Slow or async work? Schedule it and return immediately so the
    # stream keeps moving. Errors surface on the task, not on ingest.
    asyncio.create_task(_send_to_audit_log(event))


async def _send_to_audit_log(event) -> None:
    # Stand-in for a real async client (asyncpg, aiohttp webhook, etc.).
    ...


def build_with_hook():
    return RetrievalRuntime(
        chunker=RecursiveCharacterChunker(chunk_size=800),
        embedder=OpenAIEmbedding(),
        store=VectorStore(InMemoryVectorBackend()),
        on_ingest=audit,
    )
```

The callback runs inline with the ingest stream. For anything async or slow (DB writes, HTTP webhooks), wrap the body in `asyncio.create_task(...)` so the stream keeps moving and errors then surface on the task instead of bubbling out of the ingest call.

______________________________________________________________________

## Token guard

Embedding providers reject oversize inputs server-side. `max_tokens` drops those chunks pre-flight and surfaces them as `EmbeddingFailure` events instead of provider 400s:

```python
def build_with_token_guard():
    # Chunks above 8000 tokens are dropped pre-flight and surface as
    # EmbeddingFailure events rather than provider-side 400s. A default
    # TiktokenTokenizer is wired up automatically when max_tokens is set.
    return RetrievalRuntime(
        chunker=RecursiveCharacterChunker(chunk_size=2000),
        embedder=OpenAIEmbedding(model="text-embedding-3-small"),
        store=VectorStore(InMemoryVectorBackend()),
        max_tokens=8000,  # OpenAI's text-embedding-3 hard cap is 8191
    )
```

When `max_tokens` is set without a tokenizer, `RetrievalRuntime` wires up `TiktokenTokenizer` automatically. Override with `tokenizer=...` if you need a non-OpenAI tokenizer.

**Pick the limit conservatively.** OpenAI's text-embedding-3 family caps at 8191 tokens; setting `max_tokens=8000` leaves headroom for whatever the provider counts differently than tiktoken.

______________________________________________________________________

## Related

- **[Retrieval](https://docs.railtracks.org/retrieval/runtime/retrieval/index.md)**: the read path: `retrieve()`, filters, scope overrides, and patterns for wiring retrieval into an agent.
- **[Components → Ingestion](https://docs.railtracks.org/retrieval/components/ingestion/base/index.md)**: the built-in loaders, the `Document` shape, custom loaders.
- **[Components → Design](https://docs.railtracks.org/retrieval/components/design/index.md)**: internals: streaming concurrency model, the `Store` protocol, stage contracts.
