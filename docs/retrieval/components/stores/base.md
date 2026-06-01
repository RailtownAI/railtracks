# Stores

A **store** is the persistence-and-retrieval layer at the end of the
pipeline. After chunks are embedded, the store accepts `StoreEntry`
objects, indexes them, and answers `StoreQuery` requests with ranked
`RetrievedStoreEntry` results.

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

For raw vector search at the runtime level (`runtime.retrieve(...)`), see
[Retrieval](../../retrieval.md). For the backends (`InMemory`, `Chroma`,
`Pgvector`) that plug into `VectorStore`, see [Backends](backends.md).

---

## Data model

### `StoreEntry`

`StoreEntry` is the atomic unit stored and retrieved. The required fields
come straight from the embedded chunk; enrichment fields are optional and
can be filled in by a later step (a summariser, an NER pipeline, etc.).

```python
@dataclass
class StoreEntry:
    # Required — sourced from EmbeddedChunk
    id: UUID
    content: str
    vector: list[float] | None
    embedding_model: str
    chunk_id: UUID
    document_id: UUID
    # Optional enrichment
    abstract: str | None = None      # One-liner from a summariser
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
    valid_from: datetime | None = None
    valid_until: datetime | None = None
    created_at: datetime = ...       # Auto-set on construction
```

#### Building from an EmbeddedChunk

`from_chunk` is the standard constructor. It maps `EmbeddedChunk` and
`Chunk` fields automatically; enrichment fields are keyword-only.

```python
from railtracks.retrieval.stores import StoreEntry, StoreScope

entry = StoreEntry.from_chunk(
    embedded_chunk,
    scope=StoreScope(labels={"user_id": "alice"}),
    abstract="A brief summary of the chunk.",
    summary="A longer synopsis used for retrieval without full content.",
)
```

Fill in summaries later with `dataclasses.replace`:

```python
import dataclasses

enriched = dataclasses.replace(entry, abstract="…", summary="…")
```

---

### `StoreScope`

`StoreScope` is a frozen dataclass that acts as a **hard-filter
namespace**. Each entry in `labels` becomes a mandatory equality filter
on every read and clear — a query scoped to `{"user_id": "alice"}` will
never return entries written under `{"user_id": "bob"}`.

```python
@dataclass(frozen=True)
class StoreScope:
    labels: Mapping[str, Any] = field(default_factory=dict)
```

The retrieval module is agnostic about which axes you scope by — pick
whatever fits your tenancy model:

```python
StoreScope(labels={"user_id": "alice"})                              # SaaS tenancy
StoreScope(labels={"organization": "acme", "environment": "prod"})   # B2B
StoreScope(labels={"account_id": 42, "is_prod": True})               # non-string scalars
```

`StoreScope()` (no labels) matches everything — useful for single-tenant
or global stores.

---

### `Entity`

`Entity` is a frozen dataclass for named entities extracted from a chunk.
Stored in `StoreEntry.entities` and round-tripped through the payload.

```python
@dataclass(frozen=True)
class Entity:
    name: str
    type: str
    source_chunk_id: UUID
    metadata: dict = ...
```

---

### `RetrievedStoreEntry`

Every hit returned by `Store.read` is wrapped in `RetrievedStoreEntry`:

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

`StoreQuery` bundles the query text, its pre-computed embedding, and
retrieval parameters.

```python
from railtracks.retrieval.stores import StoreQuery, StoreScope

query = StoreQuery(
    text="What is the refund policy?",
    scope=StoreScope(labels={"user_id": "alice"}),
    embedding=embed("What is the refund policy?"),   # pre-computed
    top_k=5,
    metadata_filters={"source": "handbook"},
)
```

| Field | Type | Default | Description |
|---|---|---|---|
| `text` | `str` | required | Raw query string |
| `scope` | `StoreScope \| None` | `None` | Namespace filter applied to the search |
| `embedding` | `list[float] \| None` | `None` | Pre-computed query vector (required by `VectorStore`) |
| `top_k` | `int` | `10` | Maximum results to return |
| `metadata_filters` | `dict[str, Any] \| None` | `None` | Additional payload equality filters |

---

## The Store protocol

All store implementations satisfy `Store`:

```python
class Store(Protocol):
    async def write(self, entry: StoreEntry) -> str: ...
    async def read(self, query: StoreQuery) -> list[RetrievedStoreEntry]: ...
    async def delete(self, id: UUID) -> None: ...
    async def clear(self, scope: StoreScope) -> None: ...
    async def delete_where(self, filters: dict[str, Any]) -> None: ...
    async def find(self, filters: dict[str, Any], limit: int = 1) -> list[StoreEntry]: ...
```

`write` returns the entry ID as a string. `clear` removes all entries
matching the given scope — that's the path for session cleanup and user
data deletion. `delete_where` and `find` power the runtime's upsert and
staleness-detection paths (see [Design → Upsert and staleness](../design.md#upsert-and-staleness));
both operate on metadata-only equality filters.

---

## `VectorStore`

`VectorStore` is the built-in implementation. It delegates low-level
index operations to a swappable backend (in-memory, Chroma, or Pgvector)
while owning serialization and scope filtering.

```python
from railtracks.retrieval.stores import (
    InMemoryVectorBackend,
    StoreScope,
    VectorStore,
)

store = VectorStore(InMemoryVectorBackend())

await store.write(entry)
results = await store.read(query)
for r in results:
    print(r.rank, r.score, r.entry.content)

await store.delete(entry.id)
await store.clear(StoreScope(labels={"user_id": "alice"}))   # wipe one tenant
```

### `nearest_neighbors` — low-level bypass

```python
results = await store.nearest_neighbors(
    embedding=[0.1, 0.2, ...],
    k=10,
    scope=StoreScope(labels={"user_id": "alice"}),   # optional, but still enforced
)
```

Returns raw scored entries. **Scope is still enforced** — you can't skip
the multi-tenant filter by dropping to this method.

### Note on retrieved vectors

Vectors are **not** round-tripped through read results. The backend owns
the stored vector; the `vector` field on retrieved `StoreEntry` objects
is `None`. Only the original `write` call needs a populated vector.

---

## End-to-end example

From `EmbeddedChunk` to indexed entry to query result:

```python
from railtracks.retrieval.stores import (
    InMemoryVectorBackend,
    StoreEntry,
    StoreQuery,
    StoreScope,
    VectorStore,
)

store = VectorStore(InMemoryVectorBackend())
scope = StoreScope(labels={"user_id": "alice", "session_id": "s-001"})

for embedded_chunk in embedded_chunks:
    entry = StoreEntry.from_chunk(embedded_chunk, scope=scope)
    await store.write(entry)

query = StoreQuery(
    text="search text",
    scope=scope,
    embedding=query_vector,
    top_k=5,
)
results = await store.read(query)
```

---

## Next steps

- **[Backends](backends.md)** — choosing and configuring InMemory, Chroma,
  and Pgvector backends.
- **[Retrieval](../../retrieval.md)** — using `runtime.retrieve(...)` so
  you don't have to build `StoreQuery` yourself.
