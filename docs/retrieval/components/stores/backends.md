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

`ChromaBackend` and `PgvectorBackend` must be initialised before use.
Both expose an async `create(...)` factory that constructs and initialises
in one call. 

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
client modes.

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
| Suitable for | Prototyping, moderate corpora, managed Chroma Cloud |

**When to use:** standalone apps where you want a real vector index
without standing up Postgres, or when you already use Chroma Cloud.

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

|  | InMemory | Chroma | Pgvector |
|---|---|---|---|
| Extra install | None | `stores-chroma` | `stores-vector` |
| Persistence | Optional snapshot | Client-dependent | Postgres |
| Scale | Small (in-process) | Medium–Large | Large |
| Infrastructure | None | Chroma server (optional) | Postgres + pgvector |
| Best for | Tests & dev | Standalone apps | Postgres-native stacks |

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
