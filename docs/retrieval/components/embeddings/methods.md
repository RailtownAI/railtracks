# Embeddings: Built-in methods

Four embedders ship with Railtracks. The picks below are opinionated -
they reflect what works in production today, not an exhaustive enumeration.

---

## Summary

| Class | Provider | `default_batch_size` |
|---|---|---|
| `OpenAIEmbedding` | OpenAI API | `None` (set per call) |
| `AzureEmbedding` | Azure OpenAI | `None` (set per call) |
| `OllamaEmbedding` | Local Ollama | `1` |
| `LiteLLMEmbedding` | Any LiteLLM provider | `None` (set per call) |

All four inherit from `Embedding` (see [overview](index.md) for the
base class API) and are re-exported from `railtracks.retrieval.embedding`.

**Defaults you should know:**

- For production on OpenAI: `OpenAIEmbedding("text-embedding-3-small")`
  is the right starting point.
- For local development with no API costs: `OllamaEmbedding()` with
  `nomic-embed-text`.
- For anything else: `LiteLLMEmbedding(model="provider/model-name")`.

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
|---|---|
| `model` | Embedding model name. Defaults to `text-embedding-3-small`. |
| `api_key` | OpenAI API key. Falls back to `OPENAI_API_KEY`. |
| `dimensions` | Truncate vectors to this size. Only supported by `text-embedding-3-*` models. |

```python
--8<-- "docs/scripts/retrieval/embedding.py:openai"
```

**When to use:** production workloads on OpenAI. Start with
`text-embedding-3-small`; switch to `text-embedding-3-large` when
retrieval quality plateaus. Truncating dimensions on the large model
(`dimensions=256` or `512`) gives most of the quality at a fraction of
storage cost; measure before you commit to the full 3072.

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
|---|---|
| `deployment` | Azure deployment name (as configured in your Azure OpenAI resource). |
| `api_base` | Azure OpenAI endpoint (e.g. `https://my-resource.openai.azure.com`). |
| `api_version` | Azure API version (e.g. `"2024-02-01"`). |
| `api_key` | Azure API key. Falls back to `AZURE_API_KEY`. |

```python
--8<-- "docs/scripts/retrieval/embedding.py:azure"
```

**When to use:** when your organisation routes OpenAI calls through Azure
for compliance, networking, or billing reasons. Behaves identically to
`OpenAIEmbedding` at the model level; pick based on infra constraints,
not retrieval quality.

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
|---|---|
| `model` | Ollama model name. Defaults to `nomic-embed-text`. |
| `api_base` | Ollama server URL. Defaults to `http://localhost:11434`. |

`OllamaEmbedding.default_batch_size` is `1` because Ollama processes
requests sequentially: `astream_batches` becomes one API call per chunk.
That's fine for local dev; **don't use Ollama for bulk re-indexing**
unless you're prepared for the wall-clock hit.

```python
--8<-- "docs/scripts/retrieval/embedding.py:ollama"
```

**When to use:** local development without API costs, air-gapped
environments, or one-off experiments. Pull the model first:
`ollama pull nomic-embed-text`.

---

## `LiteLLMEmbedding`

The generic base the three providers above are built on. Use it directly
to reach any provider LiteLLM supports but that doesn't have a dedicated
Railtracks class (Cohere, Voyage, Mistral, Vertex AI, Bedrock, …).

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
|---|---|
| `model` | LiteLLM model string including provider prefix (e.g. `"cohere/embed-english-v3.0"`). |
| `api_key` | Provider API key. Falls back to the provider's env var. |
| `api_base` | Override the default base URL. |
| `api_version` | API version (required for some providers). |
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

To add a provider not covered above, subclass `Embedding` and implement
`aembed`:

```python
--8<-- "docs/scripts/retrieval/embedding.py:custom_async"
```

If your provider only has a blocking API, subclass `SyncEmbedding` instead
and implement `_embed_sync`. The mixin runs it in a thread pool so the
rest of the pipeline stays non-blocking:

```python
--8<-- "docs/scripts/retrieval/embedding.py:custom_sync"
```

---

## See also

- [Embeddings overview](index.md): data models, batch streaming API,
  and the `Embedding` contract.
- [Chunking overview](../components/chunking/index.md): producing
  `Chunk` objects upstream.
- [Ingestion → Token guard](../../ingestion.md#token-guard): keeping
  oversize chunks out of the provider call.
