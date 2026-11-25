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
| `StoreEntry` | Atomic unit written to and returned by the store. Its fields come from an `EmbeddedChunk`; build with `StoreEntry.from_chunk(embedded_chunk, scope=...)`. See [the field table](#storeentry). |
| `StoreScope` | Frozen `labels` dict acting as a hard-filter namespace. Every scoped read and `clear` matches entries written with exactly the same labels: `{"tenant": "alice"}` does not match `{"tenant": "alice", "env": "prod"}`. `StoreScope()` (empty) and `None` both match only unscoped entries. Reads also accept `ALL_SCOPES` to search every scope. Use it for tenancy (`user_id`, `organization`, `environment`, etc.). |
| `RetrievedStoreEntry` | A read hit: the underlying `StoreEntry` plus `score` (similarity in `[0, 1]`, higher is more similar), 0-indexed `rank`, and optional `source_retriever` / `rerank_score`. |

### `StoreEntry`

| Field | Type | Default | Description |
|---|---|---|---|
| `id` | `UUID` | required | Entry id; `write` returns it as a string. `from_chunk` uses the chunk id |
| `content` | `str` | required | Chunk text |
| `vector` | `list[float] | None` | required | Embedding to index; `None` on entries returned by reads, since the backend owns the vector |
| `embedding_model` | `str` | required | Model that produced `vector` |
| `chunk_id` | `UUID` | required | Id of the source `Chunk` |
| `document_id` | `UUID` | required | Id of the source `Document` |
| `scope` | `StoreScope | None` | `None` | Namespace the entry is written to; `None` is unscoped |
| `chunk_index` | `int` | `0` | Position of the chunk in its document |
| `parent_chunk_id` | `UUID | None` | `None` | Parent chunk, for hierarchical chunkers |
| `chunk_offsets` | `tuple[int, int] | None` | `None` | Character span of the chunk in the document |
| `chunk_metadata` | `dict` | `{}` | The chunk's metadata; scalar values are filterable |
| `embedding_version` | `str | None` | `None` | Embedding model version, if the embedder reports one |
| `created_at` | `datetime` | now (UTC) | When the entry was built |

---

## Querying

`StoreQuery` bundles the query text, its pre-computed embedding, and
retrieval parameters.

```python
--8<-- "docs/scripts/retrieval/store.py:query"
```

| Field | Type | Default | Description |
|---|---|---|---|
| `text` | `str | None` | `None` | Raw query string, kept for logging and custom stores; `VectorStore` searches by `embedding` only |
| `scope` | `StoreScope | AllScopes | None` | `None` | Namespace filter applied to the search; `None` matches only unscoped entries, `ALL_SCOPES` searches every scope |
| `embedding` | `list[float] | None` | `None` | Pre-computed query vector (required by `VectorStore`) |
| `top_k` | `int` | `10` | Maximum results to return |
| `metadata_filters` | `dict[str, Any] | None` | `None` | Additional payload equality filters, combined with the scope; the scope's key is set last, so a scoped read never returns another scope's entries |

---

## The Store protocol

All store implementations satisfy `Store`:

```python
class Store(Protocol):
    async def write(self, entry: StoreEntry) -> str: ...
    async def read(self, query: StoreQuery) -> list[RetrievedStoreEntry]: ...
    async def delete(self, id: str) -> None: ...
    async def clear(self, scope: StoreScope) -> None: ...
    async def delete_where(
        self,
        filters: dict[str, Any] | None = None,
        *,
        metadata_filters: dict[str, Any] | None = None,
    ) -> None: ...
    async def find(
        self,
        filters: dict[str, Any] | None = None,
        limit: int = 1,
        *,
        metadata_filters: dict[str, Any] | None = None,
    ) -> list[StoreEntry]: ...
    async def count(
        self,
        filters: dict[str, Any] | None = None,
        *,
        metadata_filters: dict[str, Any] | None = None,
    ) -> int: ...
```

`write` returns the entry ID as a string, and `delete` takes that string. `clear` removes all entries written with exactly the given scope (it rejects `ALL_SCOPES`); that's the path for session cleanup and user data deletion. To search by a vector you already have, call `read` with only `embedding` set (see [below](#vector-search-with-read)).

`delete_where`, `find` and `count` power the runtime's upsert and staleness-detection paths (see [Design → Upsert and staleness](../design.md#upsert-and-staleness)); they match entries by equality, without a vector search. They take two kinds of filter, and an entry must match both. If both read the same key as chunk metadata and give it different values (`1` and `True` count as different), the call raises `ValueError`. An entry-field name in `filters` and the same name in `metadata_filters` are separate keys, so no error is raised and an entry has to match both:

- **`filters`**: entry-field names (`document_id`, `chunk_id`, ...), `scope` and `scope_<label>` refer to the entry itself, and every other key refers to `chunk_metadata`.
- **`metadata_filters=`**: every key refers to `chunk_metadata` (except `scope_<label>`), the same as `StoreQuery.metadata_filters`. Use it for a metadata key that shares a name with an entry field, such as a CSV column called `document_id`.

```python
--8<-- "docs/scripts/retrieval/store.py:filters"
```

`VectorStore.delete_where` raises `ValueError` when both are empty, so a missing filter can't wipe the store; call `clear(scope)` to delete everything in a scope.

---

## `VectorStore`

`VectorStore` is the built-in implementation. It delegates low-level
index operations to a swappable backend (in-memory, Chroma, or Pgvector, etc)
while owning serialization and scope filtering.

```python
--8<-- "docs/scripts/retrieval/store.py:vs"
```

### Vector search with `read`

`StoreQuery.text` is optional, so a precomputed vector is enough to search the store directly, without the runtime:

```python
--8<-- "docs/scripts/retrieval/store.py:vector_read"
```

Returns raw scored entries. **Scope is still enforced**: calling the store directly doesn't skip the multi-tenant filter.

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
