# Store Backends

`VectorStore` delegates all index I/O to a **backend** that implements the `VectorBackend` protocol. The three built-in backends cover local development, managed vector databases, and production Postgres deployments.

```python
--8<-- "docs/scripts/vector_backends.py:protocol"
```

`ChromaBackend` and `PgvectorBackend` must be **initialised** before use. Both expose an async `create(...)` factory that constructs and initialises in one call — prefer this over calling `__init__` + `initialize()` separately:

```python
--8<-- "docs/scripts/vector_backends.py:create_factory"
```

`initialize()` is also available for cases where construction must stay synchronous (e.g. dependency injection containers):

```python
--8<-- "docs/scripts/vector_backends.py:initialize_deferred"
```

`InMemoryBackend` requires neither — it is ready immediately after construction.

---

## InMemoryBackend

A fully in-process backend backed by a Python dict. No external dependencies. Cosine similarity is computed in pure Python.

```python
--8<-- "docs/scripts/vector_backends.py:inmemory_basic"
```

### Distance metric

`InMemoryBackend` accepts the same `DistanceMetric` enum as the other backends:

```python
--8<-- "docs/scripts/vector_backends.py:inmemory_metric"
```

| `DistanceMetric` | Score formula |
|-----------------|---------------|
| `COSINE` (default) | `cosine_similarity(q, v)` |
| `L2` | `1 / (1 + ‖q - v‖)` |
| `IP` | `q · v` (raw dot product) |

### Snapshots

Snapshots let you persist the index between process restarts without any external infrastructure. Pass a `snapshot_path` and the store is saved to disk as JSON after every write or delete.

```python
--8<-- "docs/scripts/vector_backends.py:inmemory_snapshot"
```

| Property | Value |
|----------|-------|
| Install | No extra dependencies |
| Persistence | Optional JSON snapshot |
| Distance metrics | COSINE, L2, IP |
| Suitable for | Development, tests, small corpora |

---

## ChromaBackend

A backend powered by [Chroma](https://www.trychroma.com/). Supports ephemeral (in-process), persistent (on-disk), HTTP (remote server), and Chroma Cloud client modes.

```python
pip install "railtracks[stores-chroma]"
```

```python
--8<-- "docs/scripts/vector_backends.py:chroma_basic"
```

### Client modes

| Mode | When | Configuration |
|------|------|---------------|
| Ephemeral | No `path`, `host`, or cloud args | In-process, data lost on exit |
| Persistent | `path="/path/to/dir"` | Data persisted to disk |
| HTTP | `host="localhost", port=8000` | Remote Chroma server |
| Cloud | `from_cloud(...)` | Chroma Cloud (managed) |

```python
--8<-- "docs/scripts/vector_backends.py:chroma_client_modes"
```

### Chroma Cloud

Use the `from_cloud()` classmethod to connect to [Chroma Cloud](https://www.trychroma.com/). An `embedding_function` is required — Chroma Cloud stores the EF configuration server-side, and providing the object directly avoids a known reconstruction issue with certain EF configs.

```python
--8<-- "docs/scripts/vector_backends.py:chroma_cloud"
```

Any Chroma-compatible embedding function can be passed — `from_cloud()` is not tied to the Qwen EF specifically.

### Distance metric

Chroma's `hnsw:space` is set at collection creation time and cannot be changed later. The default is cosine. For Chroma Cloud collections, `metric` controls the score conversion formula only — the space is managed by the server.

```python
--8<-- "docs/scripts/vector_backends.py:chroma_metric"
```

| `DistanceMetric` | Chroma space | Score formula |
|-----------------|--------------|---------------|
| `COSINE` (default) | `cosine` | `1 - distance` |
| `L2` | `l2` | `1 / (1 + sqrt(distance))` |
| `IP` | `ip` | `1 - distance` |

| Property | Value |
|----------|-------|
| Install | `pip install "railtracks[stores-chroma]"` |
| Persistence | Via client mode |
| Distance metrics | COSINE, L2, IP |
| Suitable for | Prototyping, moderate corpora, managed Chroma Cloud |

---

## PgvectorBackend

A backend that stores entries in a Postgres table with a `pgvector` column. Requires `asyncpg` and the `pgvector` Postgres extension.

```python
pip install "railtracks[stores-vector]"
```

```python
--8<-- "docs/scripts/vector_backends.py:pgvector_basic"
```

`initialize()` (called by `create()`) runs `CREATE EXTENSION IF NOT EXISTS vector` and `CREATE TABLE IF NOT EXISTS` — safe to call on every startup.

### Dimensionality

If you know the embedding dimension upfront, pass `dim` to enable Postgres's typed vector column and let pgvector optimise the index:

```python
--8<-- "docs/scripts/vector_backends.py:pgvector_dim"
```

Without `dim`, the column is created as an untyped `vector`, which still works but cannot use `ivfflat` or `hnsw` indexes.

### Distance metric

```python
--8<-- "docs/scripts/vector_backends.py:pgvector_metric"
```

| `DistanceMetric` | SQL operator | Score formula |
|-----------------|-------------|---------------|
| `COSINE` (default) | `<=>` | `1 - distance` |
| `L2` | `<->` | `1 / (1 + distance)` |
| `IP` | `<#>` | `-distance` (dot product) |

| Property | Value |
|----------|-------|
| Install | `pip install "railtracks[stores-vector]"` |
| Persistence | Full Postgres durability |
| Distance metrics | COSINE, L2, IP |
| Suitable for | Production, existing Postgres stacks |

---

## Choosing a Backend

| | InMemory | Chroma | Pgvector |
|---|---|---|---|
| Extra install | None | `stores-chroma` | `stores-vector` |
| Persistence | Optional snapshot | Client-dependent | Postgres |
| Scale | Small (in-process) | Medium–Large | Large |
| Infrastructure | None | Chroma server (optional) | Postgres + pgvector |
| Best for | Tests & dev | Standalone apps | Postgres-native stacks |

---

## Custom Backends

Any class that satisfies the `VectorBackend` protocol can be passed to `VectorStore`. The four methods (`upsert`, `search`, `delete`, `delete_where`) are the only contract:

```python
--8<-- "docs/scripts/vector_backends.py:custom_backend"
```

`filters` is a flat `dict[str, str]` built from `StoreScope.to_payload_filters()` plus any `metadata_filters` from the query. All keys must match for an entry to be returned.
