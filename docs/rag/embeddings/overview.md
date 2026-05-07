# Embeddings Overview

Embedding is the third stage of the RAG pipeline. It takes `Chunk` objects produced by the chunker and calls a model to convert each chunk's text into a dense vector. Those vectors are what gets stored and searched.

---

## Pipeline placement

```
Source files
    ↓  Loader (ingestion)
Documents
    ↓  Chunker
Chunks
    ↓  Embedder      ← you are here
EmbeddedChunks
    ↓  Vector store
Searchable index
```

---

## The `EmbeddedChunk` object

The output of the embedding stage is a list of `EmbeddedChunk` instances — one per input chunk:

```python
@dataclass
class EmbeddedChunk:
    chunk: Chunk              # The source chunk (content, document_id, metadata, …)
    vector: list[float]       # Dense embedding vector
    embedding_model: str      # Provider-reported model name
```

`EmbeddedChunk.chunk` gives you full lineage back to the source `Document` via `chunk.document_id`.

---

## The `Embedding` contract

All providers inherit from `Embedding`. The only method subclasses must implement is `aembed`:

```python
class Embedding(ABC):
    default_batch_size: int | None = None   # subclasses should set this

    async def aembed(self, texts: list[str]) -> TextEmbeddings: ...
    def embed(self, texts: list[str]) -> TextEmbeddings: ...         # sync wrapper
```

`aembed` takes a flat list of strings and returns a `TextEmbeddings` containing the raw vectors and per-call metrics.

`embed` is a convenience sync wrapper. It raises if called from a running event loop (including Jupyter) — use `await embedder.aembed(texts)` in async contexts.

---

## Data models

### `TextEmbeddings`

The return type of `aembed`. Holds the raw float vectors alongside usage metrics:

```python
@dataclass
class TextEmbeddings:
    vectors: list[list[float]]
    metrics: EmbeddingMetrics
```

### `EmbeddingMetrics`

Every embedding call returns an `EmbeddingMetrics` object. Fields are populated when the provider reports them — some providers omit cost or token counts:

```python
@dataclass
class EmbeddingMetrics:
    input_tokens: int | None    # Tokens consumed, if reported
    total_cost: float | None    # USD cost, if reported
    latency: float              # Wall-clock seconds for the call
    vector_count: int           # Number of vectors returned
    model: str | None           # Provider-reported model name
    dimension: int | None       # Vector dimensionality
```

Metrics from multiple batches can be summed with `+`:

```python
total: EmbeddingMetrics = sum(results, start=EmbeddingMetrics())
```

Adding metrics from different models or different vector dimensions raises `ValueError`.

### `EmbeddingResult` and `EmbeddingFailure`

When using the batch streaming API, each batch yields one of these two types:

```python
@dataclass
class EmbeddingResult:
    chunks: list[EmbeddedChunk]   # Successfully embedded chunks
    metrics: EmbeddingMetrics

@dataclass
class EmbeddingFailure:
    chunks: list[Chunk]           # Source chunks that could not be embedded
    errors: list[Exception]       # Exceptions raised
```

---

## Batch streaming API

For large inputs — ingestion pipelines, bulk re-indexing — use `astream_batches` rather than calling `aembed` directly. It splits the input into fixed-size batches and yields results as each batch completes. Failures do not stop the stream; a failed batch yields an `EmbeddingFailure` so you can log and continue.

```python
from railtracks.retrieval.embedding import OpenAIEmbedding, EmbeddingResult, EmbeddingFailure

embedder = OpenAIEmbedding()

async for result in embedder.astream_batches(chunks, batch_size=100):
    if isinstance(result, EmbeddingResult):
        await vector_store.add(result.chunks)
        print(result.metrics)
    else:
        print(f"Batch failed: {result.errors}")
```

`batch_size` falls back to `default_batch_size` when omitted. Providers set a sensible class-level default; `OllamaEmbedding` sets it to `1` because Ollama processes one request at a time. If neither is set, `astream_batches` raises `ValueError`.

The input can be a plain `list[Chunk]` or an `AsyncIterable[Chunk]` — the latter lets you pipe directly from a chunker's async generator without materialising the full list.

---

## `SyncEmbedding` — wrapping blocking providers

If a provider only exposes a synchronous API, subclass `SyncEmbedding` and implement `_embed_sync`. The mixin runs it in a thread pool via `asyncio.to_thread`, keeping the rest of the pipeline non-blocking:

```python
from railtracks.retrieval.embedding import SyncEmbedding, TextEmbeddings

class MyBlockingEmbedder(SyncEmbedding):
    default_batch_size = 64

    def _embed_sync(self, texts: list[str]) -> TextEmbeddings:
        vectors = my_blocking_client.encode(texts)
        return TextEmbeddings(vectors=vectors)
```

---

## Quickstart

```python
from railtracks.retrieval.embedding import OpenAIEmbedding

embedder = OpenAIEmbedding()  # reads OPENAI_API_KEY from environment

result = await embedder.aembed(["Railtracks is a Python agent framework."])
print(result.vectors[0][:5])   # first 5 dims of the vector
print(result.metrics)
```

---

## Next steps

- **[Built-in Methods](methods.md)** — all provider classes, parameters, and when to use each.
- **[Chunking overview](../components/chunking/overview.md)** — producing `Chunk` objects upstream.
