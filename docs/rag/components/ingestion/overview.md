# Ingestion Overview

Ingestion is the first step in a RAG pipeline. A **document loader** reads raw data from a source; file, directory, URL, database, and converts it into a list of [`Document`](#the-document-object) objects that the rest of the pipeline (chunking, embedding, storage) can consume.

---

## The Document Object

Every loader produces `Document` instances:

```python
@dataclass
class Document:
    content: str               # Raw text extracted from the source
    type: DocumentType         # "text", "markdown", "csv", "pdf", "json", "html", "code"
    id: UUID                   # Auto-generated unique identifier
    source: str | None         # File path or URL the document came from
    metadata: dict             # Loader-specific key/value pairs (page number, language, …)
```

---

## Available Loaders

| Loader | Handles | Extra install? |
|--------|---------|----------------|
| `TextLoader` | `.txt`, `.md` files & directories | No |
| `CSVLoader`  | `.csv` files & directories | No |
| `PyPDFLoader` | `.pdf` files & directories | `pip install "railtracks[pdf]"` |
| `HTMLLoader`  | HTML files & URLs | `pip install "railtracks[html]"` |
| `CodeLoader`  | Source code files | No |
| `JSONLoader`  | `.json` files & directories | No |
| `LangChainLoaderAdapter` | Any LangChain loader | Depends on wrapped loader |

---

## Loading Documents

All loaders share the same interface. Use `load()` for synchronous use, `aload()` to collect all documents at once in an async context, or `astream()` to process documents one at a time as they become ready:

```python
from railtracks.retrieval.loaders import TextLoader

loader = TextLoader("docs/")
docs = loader.load()                         # sync, returns list[Document]

# async — collect all at once
docs = await loader.aload()

# async — process one at a time (preferred for large corpora)
async for doc in loader.astream():
    print(doc.source, doc.type, len(doc.content))
```

---

## What Happens Next

Documents produced by loaders feed directly into the **chunking** step, which splits them into smaller `Chunk` objects before embedding and storage.

```
Source files
    ↓  Loader (ingestion)
Documents
    ↓  Chunker
Chunks
    ↓  Embedder + Vector Store
Searchable index
```

See the [Chunking overview](../chunking/overview.md) for the next step.
