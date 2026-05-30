# Store Backends

`VectorStore` delegates all index I/O to a **backend** that implements the `VectorBackend` protocol. The three built-in backends cover local development, managed vector databases, and production Postgres deployments.

```python
class VectorBackend(Protocol):
    async def upsert(self, id: str, vector: list[float], payload: dict) -> None: ...
    async def search(self, vector: list[float], top_k: int, filters: dict) -> list[tuple[str, float, dict]]: ...
    async def delete(self, id: str) -> None: ...
    async def delete_where(self, filters: dict) -> None: ...
```

`ChromaBackend` and `PgvectorBackend` must be **initialised** before use. Both expose an async `create(...)` factory that constructs and initialises in one call — prefer this over calling `__init__` + `initialize()` separately:

```python
backend = await PgvectorBackend.create(dsn="postgresql://...", table="my_index", dim=1536)
```

`initialize()` is also available for cases where construction must stay synchronous (e.g. dependency injection containers):

```python
backend = PgvectorBackend(dsn="postgresql://...")
await backend.initialize()
```

`InMemoryBackend` requires neither — it is ready immediately after construction.

---

## InMemoryBackend

A fully in-process backend backed by a Python dict. No external dependencies. Cosine similarity is computed in pure Python.

```python
from railtracks.retrieval.stores import VectorStore, InMemoryVectorBackend

store = VectorStore(InMemoryVectorBackend())
```

### Distance metric

`InMemoryBackend` accepts the same `DistanceMetric` enum as the other backends:

```python
from railtracks.retrieval.stores.vector.metric import DistanceMetric
from railtracks.retrieval.stores.vector.backends import InMemoryBackend

backend = InMemoryBackend(metric=DistanceMetric.L2)
```

| `DistanceMetric` | Score formula |
|-----------------|---------------|
| `COSINE` (default) | `cosine_similarity(q, v)` |
| `L2` | `1 / (1 + ‖q - v‖)` |
| `IP` | `q · v` (raw dot product) |

### Snapshots

Snapshots let you persist the index between process restarts without any external infrastructure. Pass a `snapshot_path` and the store is saved to disk as JSON after every write or delete.

```python
from pathlib import Path
from railtracks.retrieval.stores.vector.backends import InMemoryBackend

store = VectorStore(InMemoryBackend(snapshot_path=Path("index.json")))

# The file is loaded automatically on next construction
store2 = VectorStore(InMemoryBackend(snapshot_path=Path("index.json")))
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
from railtracks.retrieval.stores import VectorStore, ChromaBackend

# Preferred: create() constructs and initialises in one step
backend = await ChromaBackend.create("my-collection")
store = VectorStore(backend)
```

### Client modes

| Mode | When | Configuration |
|------|------|---------------|
| Ephemeral | No `path`, `host`, or cloud args | In-process, data lost on exit |
| Persistent | `path="/path/to/dir"` | Data persisted to disk |
| HTTP | `host="localhost", port=8000` | Remote Chroma server |
| Cloud | `from_cloud(...)` | Chroma Cloud (managed) |

```python
# Persistent
backend = ChromaBackend("my-collection", path="/data/chroma")

# Remote
backend = ChromaBackend("my-collection", host="chroma.internal", port=8000)
```

### Chroma Cloud

Use the `from_cloud()` classmethod to connect to [Chroma Cloud](https://www.trychroma.com/). An `embedding_function` is required — Chroma Cloud stores the EF configuration server-side, and providing the object directly avoids a known reconstruction issue with certain EF configs.

```python
from chromadb.utils.embedding_functions.chroma_cloud_qwen_embedding_function import (
    ChromaCloudQwenEmbeddingFunction,
    ChromaCloudQwenEmbeddingModel,
)
from railtracks.retrieval.stores import VectorStore, ChromaBackend

ef = ChromaCloudQwenEmbeddingFunction(
    model=ChromaCloudQwenEmbeddingModel.QWEN3_EMBEDDING_0p6B,
    task="nl_to_code",
    api_key_env_var="CHROMA_API_KEY",  # reads from environment
)

backend = await ChromaBackend.from_cloud(
    "my-collection",
    api_key="ck-...",
    tenant="your-tenant-id",
    database="your-database",
    embedding_function=ef,
)
store = VectorStore(backend)
```

Any Chroma-compatible embedding function can be passed — `from_cloud()` is not tied to the Qwen EF specifically.

### Distance metric

Chroma's `hnsw:space` is set at collection creation time and cannot be changed later. The default is cosine. For Chroma Cloud collections, `metric` controls the score conversion formula only — the space is managed by the server.

```python
from railtracks.retrieval.stores.vector.metric import DistanceMetric

backend = ChromaBackend("my-collection", metric=DistanceMetric.L2)
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
from railtracks.retrieval.stores import VectorStore, PgvectorBackend

# Preferred: create() constructs and initialises in one step
backend = await PgvectorBackend.create(dsn="postgresql://user:pass@localhost/mydb")
store = VectorStore(backend)
```

`initialize()` (called by `create()`) runs `CREATE EXTENSION IF NOT EXISTS vector` and `CREATE TABLE IF NOT EXISTS` — safe to call on every startup.

### Dimensionality

If you know the embedding dimension upfront, pass `dim` to enable Postgres's typed vector column and let pgvector optimise the index:

```python
backend = PgvectorBackend(
    dsn="postgresql://user:pass@localhost/mydb",
    dim=1536,   # e.g. text-embedding-3-small
)
```

Without `dim`, the column is created as an untyped `vector`, which still works but cannot use `ivfflat` or `hnsw` indexes.

### Distance metric

```python
from railtracks.retrieval.stores.vector.metric import DistanceMetric

backend = PgvectorBackend(dsn="...", metric=DistanceMetric.IP)
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

`filters` is a flat `dict[str, str]` built from `StoreScope.to_payload_filters()` plus any `metadata_filters` from the query. All keys must match for an entry to be returned.
