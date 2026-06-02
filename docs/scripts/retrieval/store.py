from railtracks.retrieval.models import EmbeddedChunk
from railtracks.retrieval.stores import StoreQuery, StoreScope, StoreEntry
from railtracks.retrieval.embedding import OpenAIEmbedding

embedder = OpenAIEmbedding()

# --8<-- [start:query]
query = StoreQuery(
    text="What is the refund policy?",
    scope=StoreScope(labels={"user_id": "alice"}),
    embedding=embedder.embed(["What is the refund policy?"]).vectors[0],  # pre-computed
    top_k=5,
    metadata_filters={"source": "handbook"},
)
# --8<-- [end:query]

# --8<-- [start:vs]
from railtracks.retrieval.stores import (
    InMemoryVectorBackend,
    StoreScope,
    VectorStore,
)

store = VectorStore(InMemoryVectorBackend())

async def operations(entry: StoreEntry):
    await store.write(entry)
    results = await store.read(query)
    for r in results:
        print(r.rank, r.score, r.entry.content)

    await store.delete(entry.id)
    await store.clear(StoreScope(labels={"user_id": "alice"})) 
# --8<-- [end:vs]

# --8<-- [start:knn]
async def knn():
    results = await store.nearest_neighbors(
        embedding=embedder.embed(["What is the refund policy?"]).vectors[0],
        k=10,
        scope=StoreScope(labels={"user_id": "alice"}),   # optional, but still enforced
    )
# --8<-- [end:knn]

embedded_chunks: list[EmbeddedChunk] = []
# --8<-- [start:e2e]
from railtracks.retrieval.stores import (
    InMemoryVectorBackend,
    StoreEntry,
    StoreQuery,
    StoreScope,
    VectorStore,
)

store = VectorStore(InMemoryVectorBackend())
scope = StoreScope(labels={"user_id": "alice", "session_id": "s-001"})

async def ingest_and_query():
    for embedded_chunk in embedded_chunks:
        entry = StoreEntry.from_chunk(embedded_chunk, scope=scope)
        await store.write(entry)

    query = StoreQuery(
        text="search text",
        scope=scope,
        embedding=embedder.embed(["What is the refund policy?"]).vectors[0],
        top_k=5,
    )
    results = await store.read(query)
# --8<-- [end:e2e]

# --8<-- [start:pg]
from railtracks.retrieval.stores import PgvectorBackend
async def pgvector():
    backend = await PgvectorBackend.create(dsn="postgresql://...", table="my_index", dim=1536)
# --8<-- [end:pg]

# --8<-- [start:pg_init]
from railtracks.retrieval.stores import PgvectorBackend
async def pgvector_init():
    backend = PgvectorBackend(dsn="postgresql://...")
    await backend.initialize()
# --8<-- [end:pg_init]

# --8<-- [start:pg_dim]
backend = PgvectorBackend(
    dsn="postgresql://user:pass@localhost/mydb",
    dim=1536,   # e.g. text-embedding-3-small
)# --8<-- [end:pg_dim]

# --8<-- [start:pg_dis]
from railtracks.retrieval.stores import DistanceMetric, PgvectorBackend

backend = PgvectorBackend(dsn="...", metric=DistanceMetric.IP)
# --8<-- [end:pg_dis]

# --8<-- [start:in_memory]
from railtracks.retrieval.stores import InMemoryVectorBackend, VectorStore

store = VectorStore(InMemoryVectorBackend())
# --8<-- [end:in_memory]

# --8<-- [start:snapshot]
from pathlib import Path

from railtracks.retrieval.stores import InMemoryVectorBackend, VectorStore

store = VectorStore(InMemoryVectorBackend(snapshot_path=Path("index.json")))

# The file is loaded automatically on next construction
store2 = VectorStore(InMemoryVectorBackend(snapshot_path=Path("index.json")))
# --8<-- [end:snapshot]

# --8<-- [start:chroma]
from railtracks.retrieval.stores import ChromaBackend, VectorStore

async def chroma():
    # Prefer create(): constructs and initialises in one step
    backend = await ChromaBackend.create("my-collection")
    store = VectorStore(backend)
# --8<-- [end:chroma]

# --8<-- [start:servers]
# Persistent on-disk
backend = ChromaBackend("my-collection", path="/data/chroma")

# Remote server
backend = ChromaBackend("my-collection", host="chroma.internal", port=8000)
# --8<-- [end:servers]

# --8<-- [start:distance]
# Persistent on-disk
from railtracks.retrieval.stores import ChromaBackend, DistanceMetric

backend = ChromaBackend("my-collection", metric=DistanceMetric.L2)
# --8<-- [end:distance]

# --8<-- [start:custom]
from railtracks.retrieval.stores import VectorStore
from railtracks.retrieval.stores.vector.base import VectorBackend


class MyBackend:
    async def upsert(self, id: str, vector: list[float], payload: dict) -> None: ...

    async def search(
        self, vector: list[float], top_k: int, filters: dict
    ) -> list[tuple[str, float, dict]]: ...

    async def delete(self, id: str) -> None: ...

    async def delete_where(self, filters: dict) -> None: ...

    async def list_where(self, filters: dict, limit: int) -> list[tuple[str, dict]]: ...

    async def count(self, filters: dict) -> int: ...


store = VectorStore(MyBackend())
# --8<-- [end:custom]
