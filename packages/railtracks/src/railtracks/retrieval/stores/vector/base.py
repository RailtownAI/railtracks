from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Protocol
from uuid import UUID

from railtracks.utils.logging.create import get_rt_logger

from ..models import (
    Entity,
    RetrievedStoreEntry,
    StoreEntry,
    StoreQuery,
    StoreScope,
)

logger = get_rt_logger(__name__)


class VectorBackend(Protocol):
    async def upsert(self, id: str, vector: list[float], payload: dict) -> None: ...

    async def search(
        self, vector: list[float], top_k: int, filters: dict
    ) -> list[tuple[str, float, dict]]: ...

    async def delete(self, id: str) -> None: ...

    async def delete_where(self, filters: dict) -> None: ...

    async def list_where(self, filters: dict, limit: int) -> list[tuple[str, dict]]: ...

    async def count(self, filters: dict) -> int: ...


# ---------------------------------------------------------------------------
# Payload serialization helpers
# ---------------------------------------------------------------------------


# Keys ``_encode_chunk_metadata`` writes itself; a chunk_metadata key with one
# of these names stays in the blob so it never collides with these structural
# keys. Every other reserved key is derived from the payload at encode time.
_CHUNK_METADATA_KEYS = ("chunk_metadata", "chunk_metadata_keys")


def _is_scalar(value: object) -> bool:
    return isinstance(value, (str, int, float, bool)) or value is None


def _decode_chunk_metadata(payload: dict) -> dict:
    """Rebuild ``chunk_metadata`` from the JSON blob and the spread scalars.

    Payloads written before scalars were dropped from the blob have no
    ``chunk_metadata_keys`` and keep everything in the blob.
    """
    chunk_metadata = (
        json.loads(payload["chunk_metadata"]) if "chunk_metadata" in payload else {}
    )
    for k in json.loads(payload.get("chunk_metadata_keys", "[]")):
        # Chroma drops None-valued metadata keys on write.
        chunk_metadata[k] = payload.get(k)
    return chunk_metadata


def _encode_provenance(entry: StoreEntry) -> dict:
    out: dict = {}
    if entry.parent_chunk_id is not None:
        out["parent_chunk_id"] = str(entry.parent_chunk_id)
    if entry.chunk_offsets is not None:
        out["chunk_offsets"] = json.dumps(list(entry.chunk_offsets))
    if entry.embedding_version is not None:
        out["embedding_version"] = entry.embedding_version
    return out


def _encode_chunk_metadata(entry: StoreEntry, reserved: set[str]) -> dict:
    """Encode ``chunk_metadata`` into payload keys, skipping ``reserved`` names.

    Scalars are spread at the top level so they are filterable via
    ``metadata_filters`` / ``find``, with their keys recorded in
    ``chunk_metadata_keys`` for the read back. A key that collides with an
    already-written payload key (an entry field or a structural blob key) or
    falls in the ``scope_*`` namespace stays in the JSON blob instead, so
    neither value overwrites the other. Non-scalars also go in the blob, so
    nothing is stored twice. This runs last in ``_entry_to_payload`` so
    ``reserved`` can just be the keys the entry fields already produced — no
    hand-kept list to drift. ``scope_*`` is the one exception: it is a reserved
    *namespace* (``_payload_to_entry`` rebuilds ``scope`` from every ``scope_*``
    key), so it is excluded by prefix regardless of which labels the entry set.
    """
    if not entry.chunk_metadata:
        return {}
    reserved = reserved | set(_CHUNK_METADATA_KEYS)
    out: dict = {}
    scalars = {
        k: v
        for k, v in entry.chunk_metadata.items()
        if _is_scalar(v) and k not in reserved and not k.startswith("scope_")
    }
    rest = {k: v for k, v in entry.chunk_metadata.items() if k not in scalars}
    if scalars:
        out.update(scalars)
        out["chunk_metadata_keys"] = json.dumps(list(scalars))
    if rest:
        out["chunk_metadata"] = json.dumps(rest)
    return out


def _encode_enrichment(entry: StoreEntry) -> dict:
    out: dict = {}
    if entry.scope is not None:
        out.update(entry.scope.to_payload_filters())
    if entry.abstract is not None:
        out["abstract"] = entry.abstract
    if entry.summary is not None:
        out["summary"] = entry.summary
    if entry.valid_from is not None:
        out["valid_from"] = entry.valid_from.isoformat()
    if entry.valid_until is not None:
        out["valid_until"] = entry.valid_until.isoformat()
    if entry.entities is not None:
        out["entities"] = json.dumps(
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
    return out


def _entry_to_payload(entry: StoreEntry) -> dict:
    payload: dict = {
        "content": entry.content,
        "chunk_id": str(entry.chunk_id),
        "document_id": str(entry.document_id),
        "chunk_index": entry.chunk_index,
        "embedding_model": entry.embedding_model,
        "created_at": entry.created_at.isoformat(),
    }
    payload.update(_encode_provenance(entry))
    payload.update(_encode_enrichment(entry))
    # Spread chunk_metadata last so it can skip the keys the fields above
    # already claimed, keeping those collisions in the blob.
    payload.update(_encode_chunk_metadata(entry, reserved=set(payload)))
    return payload


def _payload_to_entry(id: str, payload: dict) -> StoreEntry:
    offsets_raw = payload.get("chunk_offsets")
    offsets: tuple[int, int] | None = None
    if offsets_raw is not None:
        parsed = (
            json.loads(offsets_raw) if isinstance(offsets_raw, str) else offsets_raw
        )
        offsets = (int(parsed[0]), int(parsed[1]))

    parent_chunk_id_raw = payload.get("parent_chunk_id")
    parent_chunk_id = UUID(parent_chunk_id_raw) if parent_chunk_id_raw else None

    chunk_metadata = _decode_chunk_metadata(payload)

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

    created_at_raw = payload.get("created_at")
    created_at = (
        datetime.fromisoformat(created_at_raw)
        if created_at_raw
        else datetime.now(tz=timezone.utc)
    )

    return StoreEntry(
        id=UUID(id),
        content=payload["content"],
        # Read results do not round-trip the vector — the backend owns it.
        vector=None,
        embedding_model=payload["embedding_model"],
        chunk_id=UUID(payload["chunk_id"]),
        document_id=UUID(payload["document_id"]),
        chunk_index=int(payload.get("chunk_index", 0)),
        abstract=payload.get("abstract"),
        summary=payload.get("summary"),
        scope=StoreScope(
            labels={
                k.removeprefix("scope_"): v
                for k, v in payload.items()
                if k.startswith("scope_")
            }
        ),
        embedding_version=payload.get("embedding_version"),
        parent_chunk_id=parent_chunk_id,
        chunk_offsets=offsets,
        chunk_metadata=chunk_metadata,
        entities=entities,
        valid_from=valid_from,
        valid_until=valid_until,
        created_at=created_at,
    )


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
        if entry.vector is None:
            raise ValueError(
                f"VectorStore.write requires entry.vector to be set "
                f"(entry_id={entry.id}); embed the chunk before writing."
            )
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

        filters: dict[str, Any] = (
            query.scope.to_payload_filters() if query.scope is not None else {}
        )
        if query.metadata_filters:
            filters.update(query.metadata_filters)

        raw_hits = await self._backend.search(query.embedding, query.top_k, filters)

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

    async def delete(self, id: UUID) -> None:
        await self._backend.delete(str(id))

    async def clear(self, scope: StoreScope) -> None:
        await self._backend.delete_where(scope.to_payload_filters())

    async def delete_where(self, filters: dict[str, Any]) -> None:
        await self._backend.delete_where(filters)

    async def find(self, filters: dict[str, Any], limit: int = 1) -> list[StoreEntry]:
        raw_hits = await self._backend.list_where(filters, limit)
        return [_payload_to_entry(hit_id, payload) for hit_id, payload in raw_hits]

    async def count(self, filters: dict[str, Any] | None = None) -> int:
        return await self._backend.count(filters or {})

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
