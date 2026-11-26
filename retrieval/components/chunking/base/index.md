# Chunking

Chunking turns each [`Document`](https://docs.railtracks.org/retrieval/components/ingestion/base/#the-document-object) produced by a loader into a list of smaller **`Chunk`** objects. Embedders, stores, and retrieval all operate on chunks, not whole documents.

For the chunkers that ship with Railtracks (when to pick which) see [Built-in Methods](https://docs.railtracks.org/retrieval/components/chunking/methods/index.md).

______________________________________________________________________

## The Chunk object

Every chunker returns `Chunk` instances ([Chunk API Reference](https://docs.railtracks.org/api_reference/railtracks/retrieval.html#Chunk))

`offsets`

`offsets`lets you map any chunk back to an exact substring of `Document.content` for citation-style grounding, highlight rendering, or debugging which span actually matched a query. Not every chunker can populate it; see [Built-in Methods](https://docs.railtracks.org/retrieval/components/chunking/methods/index.md) for which ones do.

______________________________________________________________________

## Layered API

Chunking is built from three reusable ideas:

| Layer           | Role                                                                      |
| --------------- | ------------------------------------------------------------------------- |
| **`Tokenizer`** | `encode` / `decode` / `count`; used by token-aware chunkers               |
| **`Splitter`**  | `split(text) -> list[str]`; reusable boundary detection                   |
| **`Chunker`**   | `chunk(document) -> list[Chunk]`; applies a splitter, enforces invariants |

Concrete chunkers live in `railtracks.retrieval.chunking`.

### Writing your own `Chunker`

Subclasses implement one abstract method:

```python
def chunk(self, document: Document) -> list[Chunk]: ...
```

The returned chunks must satisfy these invariants:

- `document_id` matches `document.id`
- `index` is dense and 0-based across the returned list
- `metadata` inherits from `document.metadata` (per-chunk extras may be overlaid on top)
- `offsets`, when set, are valid `(start, end)` ranges into `document.content`

The base class exposes `_make_chunks` as a convenience helper that enforces all of the above in one place. The shipped chunkers use it, and you should too unless you have a specific reason not to.

`chunk()` is expected to be CPU-bound

`achunk()` is derived from `chunk()` via [`asyncio.to_thread`](https://docs.python.org/3/library/asyncio-task.html#asyncio.to_thread). That keeps the event loop responsive for pure text splitting, but it ties up a worker thread per call. If your chunker genuinely needs async I/O (e.g. a remote tokenization service), override `achunk()` directly with a real async implementation rather than leaning on the default `to_thread` wrapper.

______________________________________________________________________

## Quickstart

```python
from uuid import uuid4

from railtracks.retrieval import Document, DocumentType
from railtracks.retrieval.chunking import RecursiveCharacterChunker

doc = Document(
    content=(
        "This is a sample document that will be split into multiple overlapping chunks. "
        "Chunkers are useful for breaking up large texts for retrieval and question answering. "
        "Overlaps ensure context is preserved between chunks. "
        "Feel free to adjust chunk_size and overlap to see how chunking behaves."
    ),
    type=DocumentType.TEXT,
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

```bash
Chunk #0: offsets=(0, 60), length=60
Content: 'This is a sample document that will be split into multiple overlapping chunks. '
-----
Chunk #1: offsets=(15, 75), length=60
Content: 'Chunkers are useful for breaking up large texts for retrieval and question answering. '
-----
...
```

______________________________________________________________________

## Next steps

- **[Built-in Methods](https://docs.railtracks.org/retrieval/components/chunking/methods/index.md)**: parameters, defaults, and when to use each chunker.
- **[Ingestion components](https://docs.railtracks.org/retrieval/components/ingestion/base/index.md)**: producing `Document` instances upstream.
- **[Embeddings](https://docs.railtracks.org/retrieval/components/embeddings/overview/index.md)**: vectorizing the chunks this stage produces.
