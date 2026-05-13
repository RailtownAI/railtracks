from __future__ import annotations

import dataclasses
import json
from datetime import datetime, timezone
from typing import Protocol
from uuid import UUID

from ..models import (
    DetailLevel,
    Entity,
    RetrievedStoreEntry,
    StoreCategory,
    StoreEntry,
    StoreQuery,
    StoreScope,
)


class VectorBackend(Protocol):
    async def upsert(self, id: str, vector: list[float], payload: dict) -> None: ...

    async def search(
        self, vector: list[float], top_k: int, filters: dict
    ) -> list[tuple[str, float, dict]]: ...

    async def delete(self, id: str) -> None: ...

    async def delete_where(self, filters: dict) -> None: ...


# ---------------------------------------------------------------------------
# Payload serialization helpers
# ---------------------------------------------------------------------------


def _entry_to_payload(entry: StoreEntry) -> dict:
    payload: dict = {}

    if entry.scope is not None:
        payload.update(entry.scope.to_payload_filters())

    if entry.abstract is not None:
        payload["abstract"] = entry.abstract
    if entry.summary is not None:
        payload["summary"] = entry.summary

    payload["content"] = entry.content
    payload["chunk_id"] = str(entry.chunk_id)
    payload["document_id"] = str(entry.document_id)
    payload["chunk_index"] = entry.chunk_index
    payload["embedding_model"] = entry.embedding_model
    payload["created_at"] = entry.created_at.isoformat()

    if entry.parent_chunk_id is not None:
        payload["parent_chunk_id"] = str(entry.parent_chunk_id)
    if entry.chunk_offsets is not None:
        payload["chunk_offsets"] = json.dumps(list(entry.chunk_offsets))
    if entry.chunk_metadata:
        payload["chunk_metadata"] = json.dumps(entry.chunk_metadata)
    if entry.embedding_version is not None:
        payload["embedding_version"] = entry.embedding_version
    if entry.store_category is not None:
        payload["store_category"] = entry.store_category.value
    if entry.valid_from is not None:
        payload["valid_from"] = entry.valid_from.isoformat()
    if entry.valid_until is not None:
        payload["valid_until"] = entry.valid_until.isoformat()

    if entry.entities is not None:
        payload["entities"] = json.dumps(
            [
                {
                    "name": e.name,
                    "type": e.type,
                    "source_chunk_id": str(e.source_chunk_id),
                    "metadata": e.metadata,
                }
                for e in entry.entities
            ]
        )

    return payload


def _payload_to_entry(id: str, payload: dict) -> StoreEntry:
    offsets_raw = payload.get("chunk_offsets")
    offsets: tuple[int, int] | None = None
    if offsets_raw is not None:
        parsed = json.loads(offsets_raw) if isinstance(offsets_raw, str) else offsets_raw
        offsets = (int(parsed[0]), int(parsed[1]))

    parent_chunk_id_raw = payload.get("parent_chunk_id")
    parent_chunk_id = UUID(parent_chunk_id_raw) if parent_chunk_id_raw else None

    chunk_metadata = (
        json.loads(payload["chunk_metadata"]) if "chunk_metadata" in payload else {}
    )

    entities: list[Entity] | None = None
    if "entities" in payload:
        raw = json.loads(payload["entities"])
        entities = [
            Entity(
                name=e["name"],
                type=e["type"],
                source_chunk_id=UUID(e["source_chunk_id"]),
                metadata=e.get("metadata", {}),
            )
            for e in raw
        ]

    valid_from = (
        datetime.fromisoformat(payload["valid_from"]) if "valid_from" in payload else None
    )
    valid_until = (
        datetime.fromisoformat(payload["valid_until"]) if "valid_until" in payload else None
    )

    created_at_raw = payload.get("created_at")
    created_at = (
        datetime.fromisoformat(created_at_raw)
        if created_at_raw
        else datetime.now(tz=timezone.utc)
    )

    store_category_raw = payload.get("store_category")
    store_category = StoreCategory(store_category_raw) if store_category_raw else None

    return StoreEntry(
        id=UUID(id),
        content=payload["content"],
        # Document vectors are not round-tripped through read results — the
        # backend owns the stored vector; callers should not rely on this field
        # on retrieved entries.
        vector=[],
        embedding_model=payload["embedding_model"],
        chunk_id=UUID(payload["chunk_id"]),
        document_id=UUID(payload["document_id"]),
        chunk_index=int(payload.get("chunk_index", 0)),
        abstract=payload.get("abstract"),
        summary=payload.get("summary"),
        scope=StoreScope(
            user_id=payload.get("scope_user_id"),
            agent_id=payload.get("scope_agent_id"),
            session_id=payload.get("scope_session_id"),
            run_id=payload.get("scope_run_id"),
        ),
        embedding_version=payload.get("embedding_version"),
        parent_chunk_id=parent_chunk_id,
        chunk_offsets=offsets,
        chunk_metadata=chunk_metadata,
        entities=entities,
        store_category=store_category,
        valid_from=valid_from,
        valid_until=valid_until,
        created_at=created_at,
    )


def _apply_detail_level(entry: StoreEntry, level: DetailLevel) -> StoreEntry:
    if level is DetailLevel.L2:
        return entry
    if level is DetailLevel.L1:
        return dataclasses.replace(entry, content="")
    return dataclasses.replace(entry, content="", summary="")


# ---------------------------------------------------------------------------
# VectorStore
# ---------------------------------------------------------------------------


class VectorStore:
    """Cosine similarity search over StoreEntry vectors.

    Satisfies the Store protocol. Does not inherit from any base class.
    """

    def __init__(self, backend: VectorBackend) -> None:
        self._backend = backend

    async def write(self, entry: StoreEntry) -> str:
        await self._backend.upsert(
            str(entry.id), entry.vector, _entry_to_payload(entry)
        )
        return str(entry.id)

    async def read(self, query: StoreQuery) -> list[RetrievedStoreEntry]:
        if query.embedding is None:
            raise ValueError(
                "VectorStore.read requires query.embedding to be set; "
                "caller must supply a pre-computed embedding."
            )

        filters = query.scope.to_payload_filters()
        if query.store_category is not None:
            filters["store_category"] = query.store_category.value
        if query.metadata_filters:
            filters.update(query.metadata_filters)

        raw_hits = await self._backend.search(query.embedding, query.top_k, filters)

        results: list[RetrievedStoreEntry] = []
        for rank, (hit_id, score, payload) in enumerate(raw_hits):
            entry = _payload_to_entry(hit_id, payload)
            entry = _apply_detail_level(entry, query.detail_level)
            results.append(
                RetrievedStoreEntry(
                    entry=entry,
                    score=score,
                    rank=rank,
                    source_retriever="dense",
                )
            )
        return results

    async def delete(self, id: UUID) -> None:
        await self._backend.delete(str(id))

    async def clear(self, scope: StoreScope) -> None:
        await self._backend.delete_where(scope.to_payload_filters())

    async def nearest_neighbors(
        self,
        embedding: list[float],
        k: int,
        scope: StoreScope | None = None,
    ) -> list[RetrievedStoreEntry]:
        filters = scope.to_payload_filters() if scope is not None else {}
        raw_hits = await self._backend.search(embedding, k, filters)

        results: list[RetrievedStoreEntry] = []
        for rank, (hit_id, score, payload) in enumerate(raw_hits):
            entry = _payload_to_entry(hit_id, payload)
            results.append(
                RetrievedStoreEntry(
                    entry=entry,
                    score=score,
                    rank=rank,
                    source_retriever="dense",
                )
            )
        return results
