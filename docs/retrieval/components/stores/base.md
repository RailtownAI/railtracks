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
[Retrieval](../../runtime/retrieval.md). For the backends (`InMemory`, `Chroma`,
`Pgvector`) that plug into `VectorStore`, see [Backends](backends.md).

---

## Data models

| Type | Summary |
|---|---|
| `StoreEntry` | Atomic unit written to and returned by the store. Required fields come from an `EmbeddedChunk`; build with `StoreEntry.from_chunk(...)`. Enrichment fields (`abstract`, `summary`, `entities`, validity window) are optional and can be filled in later via `dataclasses.replace`. |
| `StoreScope` | Frozen `labels` dict acting as a hard-filter namespace. Every read/clear is scoped by equality on these labels. `StoreScope()` (empty) matches everything. Use it for tenancy (`user_id`, `organization`, `environment`, etc.). |
| `Entity` | Frozen named-entity record (`name`, `type`, `source_chunk_id`, `metadata`) attached to `StoreEntry.entities`. |
| `RetrievedStoreEntry` | A read hit: the underlying `StoreEntry` plus `score` (similarity in `[0, 1]`, higher is more similar), 0-indexed `rank`, and optional `source_retriever` / `rerank_score`. |

---

## Querying

`StoreQuery` bundles the query text, its pre-computed embedding, and
retrieval parameters.

```python
--8<-- "docs/scripts/retrieval/store.py:query"
```

| Field | Type | Default | Description |
|---|---|---|---|
| `text` | `str` | required | Raw query string |
| `scope` | `StoreScope | None` | `None` | Namespace filter applied to the search |
| `embedding` | `list[float] | None` | `None` | Pre-computed query vector (required by `VectorStore`) |
| `top_k` | `int` | `10` | Maximum results to return |
| `metadata_filters` | `dict[str, Any] | None` | `None` | Additional payload equality filters |

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
matching the given scope; that's the path for session cleanup and user
data deletion. `delete_where` and `find` power the runtime's upsert and
staleness-detection paths (see [Design → Upsert and staleness](../design.md#upsert-and-staleness));
both operate on metadata-only equality filters.

---

## `VectorStore`

`VectorStore` is the built-in implementation. It delegates low-level
index operations to a swappable backend (in-memory, Chroma, or Pgvector, etc)
while owning serialization and scope filtering.

```python
--8<-- "docs/scripts/retrieval/store.py:vs"
```

### `nearest_neighbors`: low-level bypass

```python
--8<-- "docs/scripts/retrieval/store.py:knn"
```

Returns raw scored entries. **Scope is still enforced**: you can't skip
the multi-tenant filter by dropping to this method.

### Note on retrieved vectors

Vectors are **not** round-tripped through read results. The backend owns
the stored vector; the `vector` field on retrieved `StoreEntry` objects
is `None`. Only the original `write` call needs a populated vector.

---

## End-to-end example

From `EmbeddedChunk` to indexed entry to query result:

```python
--8<-- "docs/scripts/retrieval/store.py:e2e"
```

---

## Next steps

- **[Backends](backends.md)**: choosing and configuring InMemory, Chroma,
  and Pgvector backends.
- **[Retrieval](../../runtime/retrieval.md)**: using `runtime.retrieve(...)` so
  you don't have to build `StoreQuery` yourself.
