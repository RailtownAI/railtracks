# Ingestion Overview

Ingestion is the first step in a RAG pipeline. A **document loader** reads raw data from a source — file, directory, URL, database — and converts it into a list of [`Document`](#the-document-object) objects that the rest of the pipeline (chunking, embedding, storage) can consume.

---

## The Document Object

Every loader produces `Document` instances:

```python
@dataclass
class Document:
    content: str          # Raw text extracted from the source
    type: str             # Loader-assigned type: "text", "markdown", "csv", "pdf", …
    id: UUID              # Auto-generated unique identifier
    source: str | None    # File path or URL the document came from
    metadata: dict        # Loader-specific key/value pairs (page number, language, …)
```

---

## Available Loaders

| Loader | Import | Handles | Extra install? |
|--------|--------|---------|----------------|
| `TextLoader` | `from railtracks.retrieval.loaders import TextLoader` | `.txt`, `.md` files & directories | No |
| `CSVLoader` | `from railtracks.retrieval.loaders import CSVLoader` | `.csv` files & directories | No |
| `PyPDFLoader` | `from railtracks.retrieval.loaders.pdf_loader import PyPDFLoader` | `.pdf` files & directories | `pip install "railtracks[pdf]"` |
| `HTMLLoader` | `from railtracks.retrieval.loaders.html_loader import HTMLLoader` | HTML files & URLs | `pip install "railtracks[html]"` |
| `CodeLoader` | `from railtracks.retrieval.loaders import CodeLoader` | Source code files | No |
| `JSONLoader` | `from railtracks.retrieval.loaders.json_loader import JSONLoader` | `.json` files & directories | No |
| `LangChainLoaderAdapter` | `from railtracks.retrieval.loaders import LangChainLoaderAdapter` | Any LangChain loader | Depends on wrapped loader |

---

## Loading Documents

All loaders share the same interface. Call `load()` for synchronous use, or `aload()` inside an async workflow:

```python
from railtracks.retrieval.loaders import TextLoader

loader = TextLoader("docs/")
docs = loader.load()           # sync
# docs = await loader.aload()  # async

for doc in docs:
    print(doc.source, doc.type, len(doc.content))
```

`aload()` defaults to running `load()` in a thread pool — you never need to worry about blocking the event loop.

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
