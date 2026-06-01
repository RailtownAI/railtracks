# Store backends

`VectorStore` delegates all index I/O to a **backend** implementing the
`VectorBackend` protocol. Three backends ship — pick by where you are on
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
`VectorBackend` protocol — `runtime.retrieve()` behaves the same against
all of them. The choice is about where you want the index to live.

---

## Initialisation

`ChromaBackend` and `PgvectorBackend` must be initialised before use.
Both expose an async `create(...)` factory that constructs and initialises
in one call — **prefer `create()`** over manual `__init__` + `initialize()`:

```python
backend = await PgvectorBackend.create(dsn="postgresql://...", table="my_index", dim=1536)
```

`initialize()` is still available for cases where construction must stay
synchronous (dependency injection containers, etc.):

```python
backend = PgvectorBackend(dsn="postgresql://...")
await backend.initialize()
```

`InMemoryVectorBackend` requires neither — ready immediately after
construction.

---

## `InMemoryVectorBackend`

Fully in-process backend backed by a Python dict. No external dependencies.
Cosine similarity is computed in pure Python.

```python
from railtracks.retrieval.stores import InMemoryVectorBackend, VectorStore

store = VectorStore(InMemoryVectorBackend())
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
from pathlib import Path

from railtracks.retrieval.stores import InMemoryVectorBackend, VectorStore

store = VectorStore(InMemoryVectorBackend(snapshot_path=Path("index.json")))

# The file is loaded automatically on next construction
store2 = VectorStore(InMemoryVectorBackend(snapshot_path=Path("index.json")))
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
from railtracks.retrieval.stores import ChromaBackend, VectorStore

# Prefer create() — constructs and initialises in one step
backend = await ChromaBackend.create("my-collection")
store = VectorStore(backend)
```

### Client modes

| Mode | When | Configuration |
|---|---|---|
| Ephemeral | No `path` or `host` given | In-process, data lost on exit |
| Persistent | `path="/path/to/dir"` | Data persisted to disk |
| HTTP | `host="localhost", port=8000` | Remote Chroma server |

```python
# Persistent on-disk
backend = ChromaBackend("my-collection", path="/data/chroma")

# Remote server
backend = ChromaBackend("my-collection", host="chroma.internal", port=8000)
```

### Distance metric

Chroma's `hnsw:space` is set at collection creation and **cannot be
changed later**. Pick at create time:

```python
from railtracks.retrieval.stores import ChromaBackend, DistanceMetric

backend = ChromaBackend("my-collection", metric=DistanceMetric.L2)
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
from railtracks.retrieval.stores import PgvectorBackend, VectorStore

backend = await PgvectorBackend.create(dsn="postgresql://user:pass@localhost/mydb")
store = VectorStore(backend)
```

`initialize()` (called by `create()`) runs `CREATE EXTENSION IF NOT EXISTS
vector` and `CREATE TABLE IF NOT EXISTS` — safe to call on every startup.

### Dimensionality

If you know the embedding dimension upfront, **pass `dim`** — it enables
Postgres's typed `vector(N)` column and lets pgvector use `ivfflat` or
`hnsw` indexes:

```python
backend = PgvectorBackend(
    dsn="postgresql://user:pass@localhost/mydb",
    dim=1536,   # e.g. text-embedding-3-small
)
```

Without `dim`, the column is an untyped `vector`. Queries still work but
can't use the fast index types — fine for development, painful in
production once the table grows.

### Distance metric

```python
from railtracks.retrieval.stores import DistanceMetric, PgvectorBackend

backend = PgvectorBackend(dsn="...", metric=DistanceMetric.IP)
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
| Extra install | — | `stores-chroma` | `stores-vector` |
| Persistence | Optional snapshot | Client-dependent | Postgres |
| Scale | Small (in-process) | Medium–Large | Large |
| Infrastructure | None | Chroma server (optional) | Postgres + pgvector |
| Best for | Tests & dev | Standalone apps | Postgres-native stacks |

---

## Custom backends

Any class satisfying the `VectorBackend` protocol works with `VectorStore`.
Four methods — `upsert`, `search`, `delete`, `delete_where` — are the
entire contract.

```python
from railtracks.retrieval.stores import VectorStore
from railtracks.retrieval.stores.vector.base import VectorBackend


class MyBackend:
    async def upsert(self, id: str, vector: list[float], payload: dict) -> None:
        ...

    async def search(
        self, vector: list[float], top_k: int, filters: dict
    ) -> list[tuple[str, float, dict]]:
        # Return (id, score, payload) triples, score in [0, 1]
        ...

    async def delete(self, id: str) -> None:
        ...

    async def delete_where(self, filters: dict) -> None:
        ...


store = VectorStore(MyBackend())
```

`filters` is a flat `dict[str, str]` built from
`StoreScope.to_payload_filters()` plus any `metadata_filters` from the
query. **All keys must match** for an entry to be returned — there's no
boolean logic at the backend layer.
