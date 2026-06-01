"""
Vector store backend examples for use in documentation via --8<-- includes.

These snippets assume the relevant extras are installed:
    pip install railtracks[stores-chroma]   # for ChromaBackend
    pip install railtracks[stores-vector]   # for PgvectorBackend
"""

from typing import Protocol

from railtracks.retrieval.stores import (
    ChromaBackend,
    InMemoryVectorBackend,
    PgvectorBackend,
    VectorStore,
)
from railtracks.retrieval.stores.vector.backends import InMemoryBackend
from railtracks.retrieval.stores.vector.base import VectorBackend as _VectorBackend
from railtracks.retrieval.stores.vector.metric import DistanceMetric

# ===========================================================================
# VectorBackend protocol
# ===========================================================================

# --8<-- [start:protocol]
class VectorBackend(Protocol):
    async def upsert(self, id: str, vector: list[float], payload: dict) -> None: ...
    async def search(self, vector: list[float], top_k: int, filters: dict) -> list[tuple[str, float, dict]]: ...
    async def delete(self, id: str) -> None: ...
    async def delete_where(self, filters: dict) -> None: ...
# --8<-- [end:protocol]


# ===========================================================================
# Generic create / initialize patterns
# ===========================================================================

# --8<-- [start:create_factory]
backend = await PgvectorBackend.create(dsn="postgresql://...", table="my_index", dim=1536)
# --8<-- [end:create_factory]


# --8<-- [start:initialize_deferred]
backend = PgvectorBackend(dsn="postgresql://...")
await backend.initialize()
# --8<-- [end:initialize_deferred]


# ===========================================================================
# InMemoryBackend
# ===========================================================================

# --8<-- [start:inmemory_basic]
store = VectorStore(InMemoryVectorBackend())
# --8<-- [end:inmemory_basic]


# --8<-- [start:inmemory_metric]
backend = InMemoryBackend(metric=DistanceMetric.L2)
# --8<-- [end:inmemory_metric]


# --8<-- [start:inmemory_snapshot]
from pathlib import Path

store = VectorStore(InMemoryBackend(snapshot_path=Path("index.json")))

# The file is loaded automatically on next construction
store2 = VectorStore(InMemoryBackend(snapshot_path=Path("index.json")))
# --8<-- [end:inmemory_snapshot]


# ===========================================================================
# ChromaBackend
# ===========================================================================

# --8<-- [start:chroma_basic]
# Preferred: create() constructs and initialises in one step
backend = await ChromaBackend.create("my-collection")
store = VectorStore(backend)
# --8<-- [end:chroma_basic]


# --8<-- [start:chroma_client_modes]
# Persistent
backend = ChromaBackend("my-collection", path="/data/chroma")

# Remote
backend = ChromaBackend("my-collection", host="chroma.internal", port=8000)
# --8<-- [end:chroma_client_modes]


# --8<-- [start:chroma_cloud]
from chromadb.utils.embedding_functions.chroma_cloud_qwen_embedding_function import (
    ChromaCloudQwenEmbeddingFunction,
    ChromaCloudQwenEmbeddingModel,
)


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
# --8<-- [end:chroma_cloud]


# --8<-- [start:chroma_metric]
backend = ChromaBackend("my-collection", metric=DistanceMetric.L2)
# --8<-- [end:chroma_metric]


# ===========================================================================
# PgvectorBackend
# ===========================================================================

# --8<-- [start:pgvector_basic]
# Preferred: create() constructs and initialises in one step
backend = await PgvectorBackend.create(dsn="postgresql://user:pass@localhost/mydb")
store = VectorStore(backend)
# --8<-- [end:pgvector_basic]


# --8<-- [start:pgvector_dim]
backend = PgvectorBackend(
    dsn="postgresql://user:pass@localhost/mydb",
    dim=1536,   # e.g. text-embedding-3-small
)
# --8<-- [end:pgvector_dim]


# --8<-- [start:pgvector_metric]
backend = PgvectorBackend(dsn="...", metric=DistanceMetric.IP)
# --8<-- [end:pgvector_metric]


# ===========================================================================
# Custom backend
# ===========================================================================

# --8<-- [start:custom_backend]
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
# --8<-- [end:custom_backend]
