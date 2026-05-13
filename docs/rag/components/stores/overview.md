# Stores Overview

A **store** is the persistence and retrieval layer that sits at the end of the RAG pipeline. After chunks are embedded, a store accepts `StoreEntry` objects, indexes them by vector, and answers `StoreQuery` requests with ranked `RetrievedStoreEntry` results.

```
Chunks
    ↓  Embedder (EmbeddedChunk)
    ↓  StoreEntry.from_chunk(...)
StoreEntry objects
    ↓  Store.write(entry)
Indexed store
    ↓  Store.read(query)
list[RetrievedStoreEntry]
```

---

## Data Model

### StoreEntry

`StoreEntry` is the atomic unit stored and retrieved. The required fields come directly from the embedded chunk; enrichment fields are all optional and can be filled in after embedding by a separate enrichment step.

```python
@dataclass
class StoreEntry:
    # Required — sourced from EmbeddedChunk
    id: UUID
    content: str
    vector: list[float]
    embedding_model: str
    chunk_id: UUID
    document_id: UUID
    # Optional enrichment
    abstract: str | None = None      # One-liner produced by a summariser
    summary: str | None = None       # Mid-length synopsis
    scope: StoreScope | None = None  # Namespace / access filter
    # Optional chunk provenance
    chunk_index: int = 0
    parent_chunk_id: UUID | None = None
    chunk_offsets: tuple[int, int] | None = None
    chunk_metadata: dict = ...
    # Optional embedding provenance
    embedding_version: str | None = None
    # Optional metadata
    entities: list[Entity] | None = None
    store_category: StoreCategory | None = None
    valid_from: datetime | None = None
    valid_until: datetime | None = None
    created_at: datetime = ...       # Auto-set on construction
```

#### Building from an EmbeddedChunk

The `from_chunk` classmethod is the standard way to create a `StoreEntry` from the output of the embedding stage. It maps all `EmbeddedChunk` and `Chunk` fields automatically; enrichment fields are keyword-only overrides.

```python
from railtracks.retrieval.stores import StoreEntry, StoreScope

entry = StoreEntry.from_chunk(
    embedded_chunk,
    scope=StoreScope(user_id="alice"),
    abstract="A brief summary of the chunk.",
    summary="A longer synopsis used for retrieval without full content.",
)
```

If you do not have summaries yet, omit them and fill them in later with `dataclasses.replace`:

```python
import dataclasses
enriched = dataclasses.replace(entry, abstract="…", summary="…")
```

---

### StoreScope

`StoreScope` is a frozen dataclass that acts as a **hard-filter namespace**. Any non-`None` field is turned into a mandatory equality filter on every read and clear operation — a query scoped to `user_id="alice"` will never return entries written under `user_id="bob"`.

```python
@dataclass(frozen=True)
class StoreScope:
    user_id: str | None = None
    agent_id: str | None = None
    session_id: str | None = None
    run_id: str | None = None
```

All four fields are optional, so a `StoreScope()` with no arguments is valid and matches all entries (useful for single-tenant or global stores).

---

### StoreCategory

`StoreCategory` is a string enum that classifies entries by knowledge type. It is stored in the payload and can be used as a filter in `StoreQuery`.

| Value | Meaning |
|-------|---------|
| `EPISODIC` | Time-ordered events and logs |
| `SEMANTIC` | Factual knowledge and concepts |
| `SKILL` | How-to knowledge and procedures |
| `PROCEDURAL` | Step-by-step workflows |

```python
from railtracks.retrieval.stores import StoreCategory

entry = StoreEntry.from_chunk(embedded_chunk, store_category=StoreCategory.SEMANTIC)
```

---

### RetrievedStoreEntry

Every hit returned by `Store.read` is wrapped in a `RetrievedStoreEntry`:

```python
@dataclass
class RetrievedStoreEntry:
    entry: StoreEntry
    score: float            # Similarity score in [0, 1]; higher is more similar
    rank: int               # 0-indexed position in the result list
    source_retriever: str | None = None
    rerank_score: float | None = None
```

---

## Querying

`StoreQuery` bundles the query text, its pre-computed embedding, and retrieval parameters.

```python
from railtracks.retrieval.stores import StoreQuery, StoreScope, DetailLevel

query = StoreQuery(
    text="What is the refund policy?",
    scope=StoreScope(user_id="alice"),
    embedding=embed("What is the refund policy?"),   # pre-computed
    top_k=5,
    detail_level=DetailLevel.L2,
)
```

### DetailLevel

`DetailLevel` controls how much of each entry is returned. This is useful for multi-stage retrieval: a fast first pass at `L0` or `L1` can rank candidates before a second pass fetches full content.

| Level | Returned fields | Use case |
|-------|----------------|----------|
| `L0` | `abstract` only (`content` and `summary` blanked) | Fast first-pass ranking |
| `L1` | `abstract` + `summary` (`content` blanked) | Mid-pass re-ranking |
| `L2` | All fields including `content` | Final retrieval or single-pass |

The default is `L2`.

---

## The Store Protocol

All store implementations satisfy the `Store` protocol:

```python
class Store(Protocol):
    async def write(self, entry: StoreEntry) -> str: ...
    async def read(self, query: StoreQuery) -> list[RetrievedStoreEntry]: ...
    async def delete(self, id: UUID) -> None: ...
    async def clear(self, scope: StoreScope) -> None: ...
```

`write` returns the entry ID as a string. `clear` removes all entries matching the given scope — useful for session cleanup or user data deletion.

---

## VectorStore

`VectorStore` is the built-in implementation. It delegates the low-level index operations to a swappable **backend** (in-memory, Chroma, or Pgvector) while owning serialization, scope filtering, and detail-level projection.

```python
from railtracks.retrieval.stores import VectorStore, StoreScope
from railtracks.retrieval.stores.vector.backends import InMemoryBackend

store = VectorStore(InMemoryBackend())

# Write
await store.write(entry)

# Read
results = await store.read(query)
for r in results:
    print(r.rank, r.score, r.entry.content)

# Delete a single entry
await store.delete(entry.id)

# Wipe all entries for a user
await store.clear(StoreScope(user_id="alice"))
```

### Nearest-neighbour lookup

`VectorStore` also exposes a lower-level `nearest_neighbors` method that bypasses scope filtering and detail-level projection, returning raw scored entries:

```python
results = await store.nearest_neighbors(
    embedding=[0.1, 0.2, ...],
    k=10,
    scope=StoreScope(user_id="alice"),   # optional
)
```

### Note on retrieved vectors

Vectors are **not** round-tripped through read results. The backend owns the stored vector; the `vector` field on retrieved `StoreEntry` objects is always `[]`. Only the original `write` call needs a populated vector.

---

## Pipeline Integration

A typical end-to-end flow from `EmbeddedChunk` to indexed entry:

```python
from railtracks.retrieval.stores import VectorStore, StoreEntry, StoreScope, StoreQuery, DetailLevel
from railtracks.retrieval.stores.vector.backends import InMemoryBackend

store = VectorStore(InMemoryBackend())
scope = StoreScope(user_id="alice", session_id="s-001")

# Index
for embedded_chunk in embedded_chunks:
    entry = StoreEntry.from_chunk(embedded_chunk, scope=scope)
    await store.write(entry)

# Retrieve
query = StoreQuery(
    text="search text",
    scope=scope,
    embedding=query_vector,
    top_k=5,
)
results = await store.read(query)
```

---

## Next Steps

- **[Backends](backends.md)** — choosing and configuring InMemory, Chroma, and Pgvector backends.
