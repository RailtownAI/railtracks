# Embeddings — Built-in Methods

This page covers the embedding providers shipped with Railtracks, with constructor parameters and usage examples for each.

---

## Summary table

| Class | Import | Provider | `default_batch_size` |
|-------|--------|----------|----------------------|
| `OpenAIEmbedding` | `from railtracks.retrieval.embedding import OpenAIEmbedding` | OpenAI API | `None` (set per call) |
| `AzureEmbedding` | `from railtracks.retrieval.embedding import AzureEmbedding` | Azure OpenAI | `None` (set per call) |
| `OllamaEmbedding` | `from railtracks.retrieval.embedding import OllamaEmbedding` | Local Ollama | `1` |
| `LiteLLMEmbedding` | `from railtracks.retrieval.embedding import LiteLLMEmbedding` | Any LiteLLM provider | `None` (set per call) |

All four inherit from `Embedding`. See the [overview](overview.md) for the base class API.

---

## `OpenAIEmbedding`

```python
OpenAIEmbedding(
    model: str = "text-embedding-3-small",
    *,
    api_key: str | None = None,
    dimensions: int | None = None,
)
```

| Parameter | Description |
|-----------|-------------|
| `model` | Embedding model name. Defaults to `text-embedding-3-small`. |
| `api_key` | OpenAI API key. Falls back to `OPENAI_API_KEY`. |
| `dimensions` | Truncate vectors to this size. Only supported by `text-embedding-3-*` models. |

```python
from railtracks.retrieval.embedding import OpenAIEmbedding

# Defaults
embedder = OpenAIEmbedding()

# Large model, smaller vectors (cheaper storage)
embedder = OpenAIEmbedding(model="text-embedding-3-large", dimensions=256)
```

**When to use:** production workloads on OpenAI. `text-embedding-3-small` is the default and a good starting point; switch to `text-embedding-3-large` if you need higher retrieval quality.

---

## `AzureEmbedding`

```python
AzureEmbedding(
    deployment: str,
    *,
    api_base: str,
    api_version: str,
    api_key: str | None = None,
)
```

| Parameter | Description |
|-----------|-------------|
| `deployment` | Azure deployment name (as configured in your Azure OpenAI resource). |
| `api_base` | Azure OpenAI endpoint URL (e.g. `https://my-resource.openai.azure.com`). |
| `api_version` | Azure API version string (e.g. `"2024-02-01"`). |
| `api_key` | Azure API key. Falls back to `AZURE_API_KEY`. |

```python
from railtracks.retrieval.embedding import AzureEmbedding

embedder = AzureEmbedding(
    deployment="my-embedding-deployment",
    api_base="https://my-resource.openai.azure.com",
    api_version="2024-02-01",
)
```

**When to use:** when your organisation routes OpenAI calls through Azure for compliance or networking reasons.

---

## `OllamaEmbedding`

```python
OllamaEmbedding(
    model: str = "nomic-embed-text",
    *,
    api_base: str = "http://localhost:11434",
)
```

| Parameter | Description |
|-----------|-------------|
| `model` | Ollama model name. Defaults to `nomic-embed-text`. |
| `api_base` | Ollama server URL. Defaults to `http://localhost:11434`. |

`OllamaEmbedding.default_batch_size` is `1` because Ollama processes requests sequentially. When using `astream_batches`, each chunk becomes its own API call.

```python
from railtracks.retrieval.embedding import OllamaEmbedding

# Local server, default model
embedder = OllamaEmbedding()

# Different model or remote Ollama instance
embedder = OllamaEmbedding(model="mxbai-embed-large", api_base="http://gpu-box:11434")
```

**When to use:** local development without API costs, or air-gapped environments. Pull the model first with `ollama pull nomic-embed-text`.

---

## `LiteLLMEmbedding`

The generic base that the three providers above are built on. Use it directly to reach any provider that LiteLLM supports but that doesn't have a dedicated Railtracks class.

```python
LiteLLMEmbedding(
    model: str,
    api_key: str | None = None,
    api_base: str | None = None,
    api_version: str | None = None,
    **litellm_kwargs,
)
```

| Parameter | Description |
|-----------|-------------|
| `model` | LiteLLM model string including the provider prefix (e.g. `"cohere/embed-english-v3.0"`). |
| `api_key` | Provider API key. Falls back to the provider's environment variable. |
| `api_base` | Override the default base URL. |
| `api_version` | API version string (required for some providers). |
| `**litellm_kwargs` | Any additional keyword arguments forwarded to `litellm.aembedding`. |

```python
from railtracks.retrieval.embedding import LiteLLMEmbedding

embedder = LiteLLMEmbedding(
    model="cohere/embed-english-v3.0",
    api_key="...",
)
```

---

## Custom providers

To add a provider not covered above, subclass `Embedding` and implement `aembed`:

```python
from railtracks.retrieval.embedding import Embedding, TextEmbeddings, EmbeddingMetrics

class MyEmbedding(Embedding):
    default_batch_size = 64

    async def aembed(self, texts: list[str]) -> TextEmbeddings:
        vectors = await my_async_client.encode(texts)
        return TextEmbeddings(
            vectors=vectors,
            metrics=EmbeddingMetrics(vector_count=len(vectors)),
        )
```

If your provider only has a blocking API, subclass `SyncEmbedding` instead and implement `_embed_sync`. The mixin runs it in a thread pool so the rest of the pipeline stays non-blocking:

```python
from railtracks.retrieval.embedding import SyncEmbedding, TextEmbeddings

class MyBlockingEmbedding(SyncEmbedding):
    default_batch_size = 32

    def _embed_sync(self, texts: list[str]) -> TextEmbeddings:
        vectors = my_blocking_client.encode(texts)
        return TextEmbeddings(vectors=vectors)
```

---

## See also

- [Embeddings overview](overview.md) — data models, batch streaming API, and the `Embedding` contract.
- [Chunking overview](../components/chunking/overview.md) — producing `Chunk` objects upstream.
