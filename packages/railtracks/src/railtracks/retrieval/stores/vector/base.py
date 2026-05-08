from __future__ import annotations

import copy
import json
from datetime import datetime
from typing import Protocol
from uuid import UUID, uuid4

from railtracks.retrieval.models import Chunk, EmbeddedChunk

from ..models import (
    DetailLevel,
    Entity,
    MemoryEntry,
    MemoryQuery,
    MemoryScope,
    RetrievedMemoryEntry,
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


def _entry_to_payload(entry: MemoryEntry) -> dict:
    payload: dict = {}

    scope = entry.scope
    if scope.user_id is not None:
        payload["scope_user_id"] = scope.user_id
    if scope.agent_id is not None:
        payload["scope_agent_id"] = scope.agent_id
    if scope.session_id is not None:
        payload["scope_session_id"] = scope.session_id
    if scope.run_id is not None:
        payload["scope_run_id"] = scope.run_id

    payload["abstract"] = entry.abstract
    payload["summary"] = entry.summary

    if entry.memory_category is not None:
        payload["memory_category"] = entry.memory_category
    if entry.valid_from is not None:
        payload["valid_from"] = entry.valid_from.isoformat()
    if entry.valid_until is not None:
        payload["valid_until"] = entry.valid_until.isoformat()

    chunk = entry.chunk.chunk
    payload["chunk_content"] = chunk.content
    payload["chunk_id"] = str(chunk.id)
    payload["document_id"] = str(chunk.document_id)
    payload["chunk_index"] = chunk.index
    if chunk.parent_chunk_id is not None:
        payload["chunk_parent_chunk_id"] = str(chunk.parent_chunk_id)
    if chunk.offsets is not None:
        payload["chunk_offsets"] = json.dumps(list(chunk.offsets))
    if chunk.metadata:
        payload["chunk_metadata"] = json.dumps(chunk.metadata)

    payload["embedding_model"] = entry.chunk.embedding_model

    if entry.chunk.embedding_version is not None:
        payload["embedding_version"] = entry.chunk.embedding_version

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


def _payload_to_entry(id: str, vector: list[float], payload: dict) -> MemoryEntry:
    offsets_raw = payload.get("chunk_offsets")
    offsets: tuple[int, int] | None = None
    if offsets_raw is not None:
        parsed = json.loads(offsets_raw) if isinstance(offsets_raw, str) else offsets_raw
        offsets = (int(parsed[0]), int(parsed[1]))
    parent_chunk_id_raw = payload.get("chunk_parent_chunk_id")
    parent_chunk_id = UUID(parent_chunk_id_raw) if parent_chunk_id_raw else None
    metadata = (
        json.loads(payload["chunk_metadata"]) if "chunk_metadata" in payload else {}
    )

    chunk = Chunk(
        content=payload.get("chunk_content", ""),
        document_id=UUID(payload["document_id"]) if "document_id" in payload else uuid4(),
        id=UUID(payload["chunk_id"]) if "chunk_id" in payload else uuid4(),
        index=int(payload.get("chunk_index", 0)),
        parent_chunk_id=parent_chunk_id,
        offsets=offsets,
        metadata=metadata,
    )
    embedded = EmbeddedChunk(
        chunk=chunk,
        vector=vector,
        embedding_model=payload.get("embedding_model", ""),
        embedding_version=payload.get("embedding_version"),
    )

    scope = MemoryScope(
        user_id=payload.get("scope_user_id"),
        agent_id=payload.get("scope_agent_id"),
        session_id=payload.get("scope_session_id"),
        run_id=payload.get("scope_run_id"),
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
        datetime.fromisoformat(payload["valid_from"])
        if "valid_from" in payload
        else None
    )
    valid_until = (
        datetime.fromisoformat(payload["valid_until"])
        if "valid_until" in payload
        else None
    )

    return MemoryEntry(
        id=UUID(id),
        chunk=embedded,
        abstract=payload.get("abstract", ""),
        summary=payload.get("summary", ""),
        scope=scope,
        entities=entities,
        memory_category=payload.get("memory_category"),
        valid_from=valid_from,
        valid_until=valid_until,
    )


def _scope_filters(scope: MemoryScope) -> dict:
    result: dict[str, str] = {}
    if scope.user_id is not None:
        result["scope_user_id"] = scope.user_id
    if scope.agent_id is not None:
        result["scope_agent_id"] = scope.agent_id
    if scope.session_id is not None:
        result["scope_session_id"] = scope.session_id
    if scope.run_id is not None:
        result["scope_run_id"] = scope.run_id
    return result


def _apply_detail_level(entry: MemoryEntry, level: DetailLevel) -> MemoryEntry:
    if level is DetailLevel.L2:
        return entry

    entry = copy.copy(entry)
    original_embedded = entry.chunk
    original_chunk = original_embedded.chunk

    new_chunk = Chunk(
        content="",
        document_id=original_chunk.document_id,
        id=original_chunk.id,
        index=original_chunk.index,
        parent_chunk_id=original_chunk.parent_chunk_id,
        offsets=original_chunk.offsets,
        metadata=original_chunk.metadata,
    )
    new_embedded = EmbeddedChunk(
        chunk=new_chunk,
        vector=original_embedded.vector,
        embedding_model=original_embedded.embedding_model,
        embedding_version=original_embedded.embedding_version,
    )
    entry.chunk = new_embedded

    if level is DetailLevel.L0:
        entry.summary = ""

    return entry


# ---------------------------------------------------------------------------
# VectorStore
# ---------------------------------------------------------------------------


class VectorStore:
    """Cosine similarity search over EmbeddedChunk vectors.

    Satisfies the Store protocol. Does not inherit from any base class.
    """

    def __init__(self, backend: VectorBackend) -> None:
        self._backend = backend

    async def write(self, entry: MemoryEntry) -> str:
        await self._backend.upsert(
            str(entry.id), entry.chunk.vector, _entry_to_payload(entry)
        )
        return str(entry.id)

    async def read(self, query: MemoryQuery) -> list[RetrievedMemoryEntry]:
        if query.embedding is None:
            raise ValueError(
                "VectorStore.read requires query.embedding to be set; "
                "caller must supply a pre-computed embedding."
            )

        filters = _scope_filters(query.scope)
        raw_hits = await self._backend.search(query.embedding, query.top_k, filters)

        results: list[RetrievedMemoryEntry] = []
        for rank, (hit_id, score, payload) in enumerate(raw_hits):
            entry = _payload_to_entry(hit_id, query.embedding, payload)
            entry = _apply_detail_level(entry, query.detail_level)
            results.append(
                RetrievedMemoryEntry(
                    entry=entry,
                    score=score,
                    rank=rank,
                    source_retriever="dense",
                )
            )
        return results

    async def delete(self, id: UUID) -> None:
        await self._backend.delete(str(id))

    async def clear(self, scope: MemoryScope) -> None:
        await self._backend.delete_where(_scope_filters(scope))

    async def nearest_neighbors(
        self,
        embedding: list[float],
        k: int,
        scope: MemoryScope | None = None,
    ) -> list[RetrievedMemoryEntry]:
        filters = _scope_filters(scope) if scope is not None else {}
        raw_hits = await self._backend.search(embedding, k, filters)

        results: list[RetrievedMemoryEntry] = []
        for rank, (hit_id, score, payload) in enumerate(raw_hits):
            entry = _payload_to_entry(hit_id, embedding, payload)
            results.append(
                RetrievedMemoryEntry(
                    entry=entry,
                    score=score,
                    rank=rank,
                    source_retriever="dense",
                )
            )
        return results
