# Chunking

Chunking turns each [`Document`](../ingestion/index.md#the-document-object)
produced by a loader into a list of smaller **`Chunk`** objects. Embedders,
stores, and retrieval all operate on chunks, not whole documents.

For the chunkers that ship with Railtracks (when to pick which) see
[Built-in Methods](methods.md).

---

## The Chunk object

Every chunker returns `Chunk` instances:

```python
@dataclass
class Chunk:
    content: str                      # Text for this chunk
    document_id: UUID                 # Same as parent Document.id
    id: UUID                          # Unique id for this chunk
    index: int                        # 0, 1, 2, … within the parent document
    parent_chunk_id: UUID | None      # Optional hierarchical link
    offsets: tuple[int, int] | None   # (start, end) into Document.content
    metadata: dict                    # Document metadata plus chunker-specific keys
```

**`offsets` is the killer feature** — it lets you map any chunk back to an
exact substring of `Document.content` for citation-style grounding,
highlight rendering, or debugging which span actually matched a query. Not
every chunker can populate it; see [Built-in Methods](methods.md) for
which ones do.

---

## Layered API

Chunking is built from three reusable ideas:

| Layer | Role |
|---|---|
| **`Tokenizer`** | `encode` / `decode` / `count` — used by token-aware chunkers |
| **`Splitter`** | `split(text) -> list[str]` — reusable boundary detection |
| **`Chunker`** | `chunk(document) -> list[Chunk]` — applies a splitter, enforces invariants |

Concrete chunkers live in `railtracks.retrieval.chunking`. Subclasses
implement `chunk()` and build results through the protected `_make_chunks`
helper. **Always use `_make_chunks`** — it enforces `document_id`
propagation, dense 0-based indexing, metadata inheritance, and offset
sanity. Bypassing it means downstream stages get inconsistent chunks.

---

## Quickstart

```python
from uuid import uuid4

from railtracks.retrieval import Document
from railtracks.retrieval.chunking import RecursiveCharacterChunker

doc = Document(
    content=(
        "This is a sample document that will be split into multiple overlapping chunks. "
        "Chunkers are useful for breaking up large texts for retrieval and question answering. "
        "Overlaps ensure context is preserved between chunks. "
        "Feel free to adjust chunk_size and overlap to see how chunking behaves."
    ),
    type="text",
    id=uuid4(),
    source="example.txt",
    metadata={"author": "Test User"},
)

chunks = RecursiveCharacterChunker(chunk_size=60, overlap=15).chunk(doc)

for c in chunks:
    print(f"Chunk #{c.index}: offsets={c.offsets}, length={len(c.content)}")
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
...
```

---

## Next steps

- **[Built-in Methods](methods.md)** — parameters, defaults, and when to
  use each chunker.
- **[Ingestion components](../ingestion/index.md)** — producing
  `Document` instances upstream.
- **[Embeddings](../../embeddings/index.md)** — vectorizing the chunks
  this stage produces.
