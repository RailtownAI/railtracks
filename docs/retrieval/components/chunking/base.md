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
!!! note "`offsets`"
    `offsets`lets you map any chunk back to an
    exact substring of `Document.content` for citation-style grounding,
    highlight rendering, or debugging which span actually matched a query. Not
    every chunker can populate it; see [Built-in Methods](methods.md) for
    which ones do.

---

## Layered API

Chunking is built from three reusable ideas:

| Layer | Role |
|---|---|
| **`Tokenizer`** | `encode` / `decode` / `count`; used by token-aware chunkers |
| **`Splitter`** | `split(text) -> list[str]`; reusable boundary detection |
| **`Chunker`** | `chunk(document) -> list[Chunk]`; applies a splitter, enforces invariants |

Concrete chunkers live in `railtracks.retrieval.chunking`.

### Writing your own `Chunker`

Subclasses implement one abstract method:

```python
def chunk(self, document: Document) -> list[Chunk]: ...
```

The returned chunks must satisfy these invariants:

- `document_id` matches `document.id`
- `index` is dense and 0-based across the returned list
- `metadata` inherits from `document.metadata` (per-chunk extras may be
  overlaid on top)
- `offsets`, when set, are valid `(start, end)` ranges into
  `document.content`

The base class exposes `_make_chunks` as a convenience helper that
enforces all of the above in one place. The shipped chunkers use it,
and you should too unless you have a specific reason not to.

!!! warning "`chunk()` is expected to be CPU-bound"
    `achunk()` is derived from `chunk()` via
    [`asyncio.to_thread`](https://docs.python.org/3/library/asyncio-task.html#asyncio.to_thread).
    That keeps the event loop responsive for pure text splitting, but it
    ties up a worker thread per call. If your chunker genuinely needs
    async I/, e.g., a remote tokenization service., override
    `achunk()` directly with a real async implementation rather than
    leaning on the default `to_thread` wrapper.

---

## Quickstart

```python
--8<-- "docs/scripts/retrieval/chunking.py:quickstart"
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

---

## Next steps

- **[Built-in Methods](methods.md)**: parameters, defaults, and when to
  use each chunker.
- **[Ingestion components](../ingestion/index.md)**: producing
  `Document` instances upstream.
- **[Embeddings](../../embeddings/index.md)**: vectorizing the chunks
  this stage produces.
