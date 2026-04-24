# Chunking Overview

Chunking is the step that turns each [`Document`](#the-document-object) from ingestion into a list of smaller **`Chunk`** objects. Downstream stages (embedding, vector stores, retrievers) work on chunks, not whole documents.

---

## The Document Object

Chunkers take the same `Document` type produced by loaders:

```python
@dataclass
class Document:
    content: str          # Full text to split
    type: str             # e.g. "text", "markdown", "csv", "pdf", …
    id: UUID              # Stable document id (propagated to every chunk)
    source: str | None    # Path, URL, or opaque origin
    metadata: dict        # Inherited (shallow copy) onto each chunk unless overlaid
```

See the [Ingestion overview](../ingestion/overview.md) for how documents are created.

---

## The Chunk Object

Every chunker returns `Chunk` instances:

```python
@dataclass
class Chunk:
    content: str                      # Text for this chunk
    document_id: UUID                 # Same as parent Document.id
    id: UUID                          # Unique id for this chunk
    index: int                        # 0, 1, 2, … within the parent document
    parent_chunk_id: UUID | None      # Optional hierarchical link
    offsets: tuple[int, int] | None   # (start, end) into Document.content, if known
    metadata: dict                    # Document metadata plus chunker-specific keys
```

**Offsets** let you map a chunk back to an exact substring of `Document.content`. That supports highlighting in a viewer, citation-style grounding, and debugging. Some chunkers cannot populate offsets yet (see [Built-in Methods](methods.md)).

---

## Layered API

Chunking is built from three ideas:

| Layer | Role |
|-------|------|
| **`Tokenizer`** | `encode` / `decode` / `count` — used by token-window chunking |
| **`Splitter`** | `split(text) -> list[str]` — reusable boundary detection |
| **`Chunker`** | `chunk(document) -> list[Chunk]` — applies split logic and enforces invariants |

Concrete chunkers live in `railtracks.retrieval.chunking`. Subclasses implement `chunk()` and assemble output through the protected **`_make_chunks`** helper so `document_id`, dense `index`, metadata inheritance, and optional offsets stay consistent.

---

## Quickstart

```python
# Example: Chunk a document into overlapping text segments

from railtracks.retrieval import Document
from railtracks.retrieval.chunking import RecursiveCharacterChunker
from uuid import uuid4

# Sample content to chunk
text = (
    "This is a sample document that will be split into multiple overlapping chunks. "
    "Chunkers are useful for breaking up large texts for retrieval and question answering. "
    "Overlaps ensure context is preserved between chunks. "
    "Feel free to adjust chunk_size and overlap to see how chunking behaves."
)

# Create a Document instance
doc = Document(
    content=text,
    type="text",
    id=uuid4(),
    source="example.txt",
    metadata={"author": "Test User"},
)

# Choose a chunker and its parameters
chunker = RecursiveCharacterChunker(chunk_size=60, overlap=15)
chunks = chunker.chunk(doc)

# Print out information for each chunk
for c in chunks:
    print(
        f"Chunk #{c.index}: offsets={c.offsets}, length={len(c.content)}"
    )
    print(f"Content: {c.content!r}")
    print("-----")
```

```output
Chunk #0: offsets=(0, 60), length=60
Content: 'This is a sample document that will be split into multiple overlapping chunks. '
-----
Chunk #1: offsets=(15, 75), length=60
Content: 'Chunkers are useful for breaking up large texts for retrieval and question answering. '
-----
...(output continues)
```

---


## Pipeline placement

```
Source files
    ↓  Loader (ingestion)
Documents
    ↓  Chunker
Chunks
    ↓  Embedder + Vector store
Searchable index
```

---

## Next steps

- **[Built-in Methods](methods.md)** — parameters, defaults, and when to use each chunker.
- **[Ingestion overview](../ingestion/overview.md)** — producing `Document` instances upstream.
