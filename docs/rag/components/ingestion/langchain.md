# LangChain Loaders

`LangChainLoaderAdapter` wraps any [LangChain `BaseLoader`](https://reference.langchain.com/python/langchain-community/document_loaders) and normalises its output to railtracks' [`Document`](overview.md#the-document-object) model. This unlocks LangChain's large community loader ecosystem (Wikipedia, Notion, Confluence, S3, Slack, …) without having to re-implement any of them in railtracks.

The adapter does not import `langchain` itself — it duck-types on the wrapped loader. Install whichever LangChain package provides the loader you want:

```bash
pip install langchain-community
```

```python
from railtracks.retrieval.loaders import LangChainLoaderAdapter
```

---

## Basic Usage

```python
from langchain_community.document_loaders import WikipediaLoader
from railtracks.retrieval.loaders import LangChainLoaderAdapter

adapter = LangChainLoaderAdapter(
    WikipediaLoader(query="Python (programming language)"),
)

async for doc in adapter.astream():
    print(doc.source, len(doc.content))
```

Each LangChain `Document` becomes one railtracks `Document`:

- `page_content` → `Document.content`
- `metadata["source"]` is popped into `Document.source` (if present)
- The remaining `metadata` is copied across as-is

---

## Tagging the Document Type

LangChain loaders are source-agnostic, so the adapter cannot guess the right `DocumentType`. Pass it explicitly when you know what you're loading:

```python
from langchain_community.document_loaders import UnstructuredMarkdownLoader
from railtracks.retrieval.loaders import LangChainLoaderAdapter, DocumentType

adapter = LangChainLoaderAdapter(
    UnstructuredMarkdownLoader("notes.md"),
    document_type=DocumentType.MARKDOWN,
)
docs = await adapter.aload()
```

The default is `DocumentType.TEXT`.

---

## Overriding the Source

If the wrapped loader doesn't populate `metadata["source"]` — or you'd like a more meaningful label — pass `source=` to the adapter. The explicit value wins and metadata is left untouched:

```python
adapter = LangChainLoaderAdapter(
    some_lc_loader,
    source="internal://corpus/2026-q1",
)
```

---

## Streaming Behaviour

The adapter tries to stream rather than buffer, falling back gracefully when the wrapped loader doesn't support async or lazy iteration:

| Wrapped loader exposes | Adapter uses | Streams? |
|------------------------|--------------|----------|
| `alazy_load`           | `alazy_load` directly | Yes (native async) |
| `lazy_load` only       | `lazy_load` pumped from a worker thread | Yes |
| `load` only            | `load()` once, then iterates the result | No (eager) |

Every modern LangChain `BaseLoader` provides at least the default `alazy_load`, so the streaming path is the common case.

---

## Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `loader` | `Any` | — | A LangChain `BaseLoader`-compatible instance. |
| `document_type` | `DocumentType` | `DocumentType.TEXT` | Tag applied to every emitted document. |
| `source` | `str \| None` | `None` | Overrides `Document.source`. When `None`, the adapter falls back to `metadata["source"]`. |

---

## When to Reach for the Adapter

Use `LangChainLoaderAdapter` when:

- A loader you need already exists in `langchain-community` (Notion, Slack, Confluence, Sitemap, GitHub issues, …) and re-implementing it would be wasted effort.
- You're migrating a LangChain-based ingestion pipeline to railtracks and want to keep the existing loaders working unchanged.

Reach for a native railtracks loader (`TextLoader`, `PyPDFLoader`, `HuggingFaceDatasetLoader`, …) when one exists — they're better integrated and don't carry a third-party dependency.
