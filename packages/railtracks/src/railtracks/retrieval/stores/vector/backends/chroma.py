from __future__ import annotations

import asyncio
import math
from typing import Any

from typing_extensions import Self

from ..metric import DistanceMetric


def _to_chroma_where(filters: dict) -> dict:
    """Translate a flat equality dict to a Chroma where clause."""
    conditions = [{k: {"$eq": v}} for k, v in filters.items()]
    if len(conditions) == 1:
        return conditions[0]
    return {"$and": conditions}


def _chroma_to_score(metric: DistanceMetric, distance: float) -> float:
    """Convert a raw Chroma distance to a similarity score (higher = better).

    Chroma (via hnswlib) distance conventions:
        cosine  1 - cosine_similarity       → score = 1 - d
        l2      squared L2 (||a-b||²)       → score = 1 / (1 + sqrt(d))
        ip      1 - dot_product             → score = 1 - d  (= dot_product)
    """
    if metric is DistanceMetric.L2:
        return 1.0 / (1.0 + math.sqrt(distance))
    return 1.0 - distance  # COSINE and IP share the same formula


class _ChromaBase:
    """Shared Chroma I/O operations. Subclasses supply __init__ and initialize()."""

    _NOT_INITIALIZED: str = "Chroma backend is not initialized"
    _metric: DistanceMetric
    _collection: Any

    def _require_initialized(self) -> None:
        if self._collection is None:
            raise RuntimeError(self._NOT_INITIALIZED)

    async def upsert(self, id: str, vector: list[float], payload: dict) -> None:
        self._require_initialized()
        collection = self._collection
        content = payload.get("content")
        await asyncio.to_thread(
            collection.upsert,
            ids=[id],
            embeddings=[vector],
            documents=[content] if content is not None else None,
            metadatas=[payload],
        )

    async def search(
        self, vector: list[float], top_k: int, filters: dict
    ) -> list[tuple[str, float, dict]]:
        self._require_initialized()
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
            hits.append((id_, _chroma_to_score(self._metric, distance), dict(metadata)))
        return hits

    async def delete(self, id: str) -> None:
        self._require_initialized()
        collection = self._collection
        await asyncio.to_thread(collection.delete, ids=[id])

    async def delete_where(self, filters: dict) -> None:
        self._require_initialized()
        if not filters:
            return
        collection = self._collection
        where = _to_chroma_where(filters)
        await asyncio.to_thread(collection.delete, where=where)

    async def list_where(self, filters: dict, limit: int) -> list[tuple[str, dict]]:
        self._require_initialized()
        collection = self._collection
        where = _to_chroma_where(filters) if filters else None
        result = await asyncio.to_thread(
            collection.get,
            where=where,
            limit=limit,
            include=["metadatas"],
        )
        return [
            (id_, dict(metadata) if metadata is not None else {})
            for id_, metadata in zip(result["ids"], result["metadatas"])
        ]

    async def count(self, filters: dict) -> int:
        self._require_initialized()
        collection = self._collection
        if not filters:
            return await asyncio.to_thread(collection.count)
        result = await asyncio.to_thread(
            collection.get,
            where=_to_chroma_where(filters),
            include=[],
        )
        return len(result["ids"])


class ChromaBackend(_ChromaBase):
    """Chroma VectorBackend for local and self-hosted deployments.

    Wraps a single Chroma collection. All Chroma I/O is synchronous and runs
    in a thread via asyncio.to_thread. Call initialize() before any other method.

    Three client modes are selected by the constructor arguments:
      - no path/host/port  → EphemeralClient (in-process, no persistence)
      - path only          → PersistentClient (local disk)
      - host + port        → HttpClient (remote server)

    For Chroma Cloud, use ChromaCloudBackend instead.
    """

    _NOT_INITIALIZED = (
        "ChromaBackend is not initialized — "
        "call await ChromaBackend.create(...) or await backend.initialize() first"
    )

    def __init__(
        self,
        collection_name: str,
        *,
        path: str | None = None,
        host: str | None = None,
        port: int | None = None,
        metric: DistanceMetric = DistanceMetric.COSINE,
    ) -> None:
        """
        Args:
            collection_name: Name of the Chroma collection to get or create.
            path: Local directory for a PersistentClient. Mutually exclusive
                with ``host``/``port``. Omit for an in-process EphemeralClient.
            host: Hostname of a remote Chroma server (HttpClient). Requires
                ``port``.
            port: Port of the remote Chroma server. Requires ``host``.
            metric: Distance metric used for similarity search. Sets the
                ``hnsw:space`` metadata on the collection at creation time and
                cannot be changed afterwards. Defaults to cosine.
        """
        self._collection_name = collection_name
        self._path = path
        self._host = host
        self._port = port
        self._metric = metric
        self._collection = None

    @classmethod
    async def create(
        cls,
        collection_name: str,
        *,
        path: str | None = None,
        host: str | None = None,
        port: int | None = None,
        metric: DistanceMetric = DistanceMetric.COSINE,
    ) -> Self:
        """Create and initialize a ChromaBackend in one step."""
        backend = cls(collection_name, path=path, host=host, port=port, metric=metric)
        await backend.initialize()
        return backend

    async def initialize(self) -> None:
        """Create the Chroma client and collection."""
        try:
            import chromadb
        except ImportError:
            raise ImportError(
                "chromadb is required for ChromaBackend. "
                "Install it with: pip install railtracks[stores-chroma]"
            ) from None

        metric = self._metric

        def _setup():
            if self._path:
                client = chromadb.PersistentClient(path=self._path)
            elif self._host and self._port:
                client = chromadb.HttpClient(host=self._host, port=self._port)
            else:
                client = chromadb.EphemeralClient()
            return client.get_or_create_collection(
                self._collection_name,
                metadata={"hnsw:space": metric.value},
            )

        self._collection = await asyncio.to_thread(_setup)


class ChromaCloudBackend(_ChromaBase):
    """Chroma VectorBackend for Chroma Cloud.

    Wraps a single Chroma Cloud collection. All Chroma I/O is synchronous and
    runs in a thread via asyncio.to_thread. Call initialize() before any other
    method.

    Embeddings must be generated client-side (e.g. via a railtracks embedder)
    and passed as ``vector`` to every ``upsert`` and ``search`` call, just like
    the local ``ChromaBackend``.
    """

    _NOT_INITIALIZED = (
        "ChromaCloudBackend is not initialized — "
        "call await ChromaCloudBackend.create(...) or await backend.initialize() first"
    )

    def __init__(
        self,
        collection_name: str,
        *,
        api_key: str,
        tenant: str,
        database: str,
        metric: DistanceMetric = DistanceMetric.COSINE,
    ) -> None:
        """
        Args:
            collection_name: Name of the Chroma Cloud collection to get or
                create.
            api_key: Chroma Cloud API key (``chk-...``).
            tenant: Chroma Cloud tenant ID.
            database: Chroma Cloud database name.
            metric: Distance metric used for score conversion. Unlike local
                backends, this does **not** set ``hnsw:space`` — the index
                space is managed server-side. Defaults to cosine.
        """
        self._collection_name = collection_name
        self._api_key = api_key
        self._tenant = tenant
        self._database = database
        self._metric = metric
        self._collection = None

    @classmethod
    async def create(
        cls,
        collection_name: str,
        *,
        api_key: str,
        tenant: str,
        database: str,
        metric: DistanceMetric = DistanceMetric.COSINE,
    ) -> Self:
        """Create and initialize a ChromaCloudBackend in one step."""
        backend = cls(
            collection_name,
            api_key=api_key,
            tenant=tenant,
            database=database,
            metric=metric,
        )
        await backend.initialize()
        return backend

    async def initialize(self) -> None:
        """Create the Chroma Cloud client and collection."""
        try:
            import chromadb
        except ImportError:
            raise ImportError(
                "chromadb is required for ChromaCloudBackend. "
                "Install it with: pip install railtracks[stores-chroma]"
            ) from None

        api_key = self._api_key
        tenant = self._tenant
        database = self._database
        collection_name = self._collection_name

        def _setup():
            client = chromadb.CloudClient(
                api_key=api_key,
                tenant=tenant,
                database=database,
            )
            return client.get_or_create_collection(collection_name)

        self._collection = await asyncio.to_thread(_setup)
