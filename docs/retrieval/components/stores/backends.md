# Store backends

`VectorStore` delegates all index I/O to a **backend** implementing the
`VectorBackend` protocol. Three backends ship; pick by where you are on
the dev → production curve.

```python
class VectorBackend(Protocol):
    async def upsert(self, id: str, vector: list[float], payload: dict) -> None: ...
    async def search(
        self, vector: list[float], top_k: int, filters: dict
    ) -> list[tuple[str, float, dict]]: ...
    async def delete(self, id: str) -> None: ...
    async def delete_where(self, filters: dict) -> None: ...
```

**Pick by infra, not features.** All three backends speak the same
`VectorBackend` protocol; `runtime.retrieve()` behaves the same against
all of them. The choice is about where you want the index to live.

---

## Initialization

`ChromaBackend`, `ChromaCloudBackend`, and `PgvectorBackend` must be
initialised before use. All three expose an async `create(...)` factory
that constructs and initialises in one call.

**Prefer `create()`** over manual `__init__` + `initialize()`:

```python
--8<-- "docs/scripts/retrieval/store.py:pg"
```

`initialize()` is still available for cases where construction must stay
synchronous (dependency injection containers, etc.):

```python
--8<-- "docs/scripts/retrieval/store.py:pg_init"
```

`InMemoryVectorBackend` requires neither; ready immediately after
construction.

---

## `InMemoryVectorBackend`

Fully in-process backend backed by a Python dict. No external dependencies.
Cosine similarity is computed in pure Python.

```python
--8<-- "docs/scripts/retrieval/store.py:in_memory"
```

### Distance metric

Same `DistanceMetric` enum as the other backends:

```python
from railtracks.retrieval.stores import DistanceMetric, InMemoryVectorBackend

backend = InMemoryVectorBackend(metric=DistanceMetric.L2)
```

| `DistanceMetric` | Score formula |
|---|---|
| `COSINE` (default) | `cosine_similarity(q, v)` |
| `L2` | `1 / (1 + ‖q - v‖)` |
| `IP` | `q · v` (raw dot product) |

### Snapshots

Snapshots persist the index between process restarts without external
infrastructure. Pass `snapshot_path` and the store is saved to disk as
JSON after every write or delete:

```python
--8<-- "docs/scripts/retrieval/store.py:snapshot"
```

| Property | Value |
|---|---|
| Install | No extra dependencies |
| Persistence | Optional JSON snapshot |
| Distance metrics | COSINE, L2, IP |
| Suitable for | Development, tests, small corpora |

**When to use:** unit tests, demos, small (<100k chunks) single-process
workloads. If you're snapshotting more than once a second, you've
outgrown this backend.

---

## `ChromaBackend`

Backend powered by [Chroma](https://www.trychroma.com/). Supports
ephemeral (in-process), persistent (on-disk), and HTTP (remote server)
client modes. For Chroma Cloud, use [`ChromaCloudBackend`](#chromacloudbackend).

```bash
pip install "railtracks[stores-chroma]"
```

```python
--8<-- "docs/scripts/retrieval/store.py:chroma"
```

### Client modes

| Mode | When | Configuration |
|---|---|---|
| Ephemeral | No `path` or `host` given | In-process, data lost on exit |
| Persistent | `path="/path/to/dir"` | Data persisted to disk |
| HTTP | `host="localhost", port=8000` | Remote Chroma server |

```python
--8<-- "docs/scripts/retrieval/store.py:servers"
```

### Documents and content

Chroma stores text alongside each vector as a *Document*. Both Chroma
backends map `StoreEntry.content` (equivalently, `Chunk.content`) to this
field automatically — you don't need to set it separately. This is what
Chroma displays in its UI and what server-side embedding functions receive.

### Distance metric

Chroma's `hnsw:space` is set at collection creation and **cannot be
changed later**. Pick at create time:

```python
--8<-- "docs/scripts/retrieval/store.py:distance"
```

| `DistanceMetric` | Chroma space | Score formula |
|---|---|---|
| `COSINE` (default) | `cosine` | `1 - distance` |
| `L2` | `l2` | `1 / (1 + sqrt(distance))` |
| `IP` | `ip` | `1 - distance` |

| Property | Value |
|---|---|
| Install | `pip install "railtracks[stores-chroma]"` |
| Persistence | Via client mode |
| Distance metrics | COSINE, L2, IP |
| Suitable for | Prototyping, moderate corpora, self-hosted Chroma |

**When to use:** standalone apps where you want a real vector index
without standing up Postgres.

---

## `ChromaCloudBackend`

Backend for [Chroma Cloud](https://www.trychroma.com/) — the managed
Chroma service. Uses the same `stores-chroma` install as `ChromaBackend`
but has a distinct constructor because the connection args are
incompatible with local/HTTP modes.

```bash
pip install "railtracks[stores-chroma]"
```

```python
--8<-- "docs/scripts/retrieval/store.py:chroma_cloud"
```

Embeddings must be generated client-side (e.g. via a railtracks embedder)
and passed as `vector` on every write and search, exactly like the local
`ChromaBackend`.

!!! note "Chroma Dashboard semantic search"
    The Chroma Cloud dashboard's built-in semantic search requires an
    embedding model to be configured on the collection server-side. If you
    want that UI feature to work, make sure the model you use to embed your
    chunks is available as a Chroma-supported embedding function and
    configure it on the collection directly via the Chroma Cloud console.

### Distance metric

For Cloud collections, `metric` controls the **score conversion formula
only** — the `hnsw:space` is managed server-side and cannot be set at
collection creation time.

```python
--8<-- "docs/scripts/retrieval/store.py:chroma_cloud_metric"
```

| `DistanceMetric` | Score formula |
|---|---|
| `COSINE` (default) | `1 - distance` |
| `L2` | `1 / (1 + sqrt(distance))` |
| `IP` | `1 - distance` |

| Property | Value |
|---|---|
| Install | `pip install "railtracks[stores-chroma]"` |
| Persistence | Managed by Chroma Cloud |
| Distance metrics | COSINE, L2, IP |
| Suitable for | Managed Chroma Cloud deployments |

**When to use:** when you want a fully managed vector store with no
infrastructure to run. Requires a Chroma Cloud account.

---

## `PgvectorBackend`

Stores entries in a Postgres table with a `pgvector` column. Requires
`asyncpg` and the `pgvector` Postgres extension.

```bash
pip install "railtracks[stores-vector]"
```

```python
--8<-- "docs/scripts/retrieval/store.py:pg"
```

`initialize()` (called by `create()`) runs `CREATE EXTENSION IF NOT EXISTS
vector` and `CREATE TABLE IF NOT EXISTS`; safe to call on every startup.

### Dimensionality

If you know the embedding dimension upfront, **pass `dim`**: it enables
Postgres's typed `vector(N)` column and lets pgvector use `ivfflat` or
`hnsw` indexes:

```python
--8<-- "docs/scripts/retrieval/store.py:pg_dim"
```

Without `dim`, the column is an untyped `vector`. Queries still work but
can't use the fast index types; fine for development, might cause issues in
production once the table grows.

### Distance metric

```python
--8<-- "docs/scripts/retrieval/store.py:pg_dis"
```

| `DistanceMetric` | SQL operator | Score formula |
|---|---|---|
| `COSINE` (default) | `<=>` | `1 - distance` |
| `L2` | `<->` | `1 / (1 + distance)` |
| `IP` | `<#>` | `-distance` (dot product) |

| Property | Value |
|---|---|
| Install | `pip install "railtracks[stores-vector]"` |
| Persistence | Full Postgres durability |
| Distance metrics | COSINE, L2, IP |
| Suitable for | Production, existing Postgres stacks |

**When to use:** anywhere you already run Postgres. One backup story, one
permissions story, one connection pool. The right default for production
unless you have a strong reason for a managed vector DB.

---

## Choosing a backend

|  | InMemory | Chroma | ChromaCloud | Pgvector |
|---|---|---|---|---|
| Extra install | None | `stores-chroma` | `stores-chroma` | `stores-vector` |
| Persistence | Optional snapshot | Client-dependent | Managed | Postgres |
| Scale | Small (in-process) | Medium–Large | Large | Large |
| Infrastructure | None | Chroma server (optional) | Chroma Cloud account | Postgres + pgvector |
| Best for | Tests & dev | Standalone apps | Managed vector DB | Postgres-native stacks |

---

## Custom backends

Any class satisfying the `VectorBackend` protocol works with `VectorStore`.
Four methods (`upsert`, `search`, `delete`, `delete_where`) are the
entire contract.

```python
--8<-- "docs/scripts/retrieval/store.py:custom"
```

`filters` is a flat `dict[str, str]` built from
`StoreScope.to_payload_filters()` plus any `metadata_filters` from the
query. **All keys must match** for an entry to be returned; there's no
boolean logic at the backend layer.
