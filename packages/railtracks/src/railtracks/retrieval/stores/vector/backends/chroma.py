from __future__ import annotations

import asyncio


_NOT_INITIALIZED = (
    "call await ChromaBackend.initialize() first and ensure chromadb is installed"
)


def _to_chroma_where(filters: dict) -> dict:
    """Translate a flat equality dict to a Chroma where clause."""
    conditions = [{k: {"$eq": v}} for k, v in filters.items()]
    if len(conditions) == 1:
        return conditions[0]
    return {"$and": conditions}


class ChromaBackend:
    """Chroma VectorBackend.

    Wraps a single Chroma collection. All Chroma I/O is synchronous and runs
    in a thread via asyncio.to_thread. Call initialize() before any other method.

    Three client modes are selected by the constructor arguments:
      - no path/host/port  → EphemeralClient (in-process, no persistence)
      - path only          → PersistentClient (local disk)
      - host + port        → HttpClient (remote server)
    """

    def __init__(
        self,
        collection_name: str,
        *,
        path: str | None = None,
        host: str | None = None,
        port: int | None = None,
    ) -> None:
        self._collection_name = collection_name
        self._path = path
        self._host = host
        self._port = port
        self._collection = None

    async def initialize(self) -> None:
        """Create the Chroma client and collection.

        Guards the chromadb import so a missing dependency raises a clear error.
        """
        try:
            import chromadb
        except ImportError:
            raise ImportError(
                "chromadb is required for ChromaBackend. "
                "Install it with: pip install railtracks[stores-chroma]"
            ) from None

        def _setup():
            if self._path:
                client = chromadb.PersistentClient(path=self._path)
            elif self._host and self._port:
                client = chromadb.HttpClient(host=self._host, port=self._port)
            else:
                client = chromadb.EphemeralClient()
            return client.get_or_create_collection(self._collection_name)

        self._collection = await asyncio.to_thread(_setup)

    async def upsert(self, id: str, vector: list[float], payload: dict) -> None:
        if self._collection is None:
            raise RuntimeError(_NOT_INITIALIZED)
        collection = self._collection
        await asyncio.to_thread(
            collection.upsert,
            ids=[id],
            embeddings=[vector],
            metadatas=[payload],
        )

    async def search(
        self, vector: list[float], top_k: int, filters: dict
    ) -> list[tuple[str, float, dict]]:
        if self._collection is None:
            raise RuntimeError(_NOT_INITIALIZED)
        collection = self._collection

        count = await asyncio.to_thread(collection.count)
        if count == 0:
            return []

        n_results = min(top_k, count)
        where = _to_chroma_where(filters) if filters else None

        results = await asyncio.to_thread(
            collection.query,
            query_embeddings=[vector],
            n_results=n_results,
            where=where,
            include=["metadatas", "distances"],
        )

        hits: list[tuple[str, float, dict]] = []
        for id_, distance, metadata in zip(
            results["ids"][0],
            results["distances"][0],
            results["metadatas"][0],
        ):
            # Chroma stores cosine distance (0 = identical, 2 = opposite).
            # Convert to similarity so higher = more relevant, consistent with
            # InMemoryBackend.
            hits.append((id_, 1.0 - distance, dict(metadata)))
        return hits

    async def delete(self, id: str) -> None:
        if self._collection is None:
            raise RuntimeError(_NOT_INITIALIZED)
        collection = self._collection
        await asyncio.to_thread(collection.delete, ids=[id])

    async def delete_where(self, filters: dict) -> None:
        if self._collection is None:
            raise RuntimeError(_NOT_INITIALIZED)
        if not filters:
            return
        collection = self._collection
        where = _to_chroma_where(filters)
        await asyncio.to_thread(collection.delete, where=where)
