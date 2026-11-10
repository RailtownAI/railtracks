from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Protocol
from uuid import UUID

from railtracks.utils.logging.create import get_rt_logger

from ..models import (
    _LABEL_VALUE_TYPES,
    AllScopes,
    Entity,
    RetrievedStoreEntry,
    StoreEntry,
    StoreQuery,
    StoreScope,
    exact_scope_filter,
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


# Scalar chunk_metadata values are spread as top-level keys with this prefix,
# so metadata can't overwrite entry fields or scope labels (mirrors scope_).
_META_PREFIX = "meta_"

# Records the (unprefixed) names of the spread metadata keys. Deliberately not
# meta_-prefixed, so a metadata key named "keys" can't collide with it.
_META_KEYS = "chunk_meta_keys"

# Top-level payload keys written from StoreEntry fields, plus _META_KEYS.
_RESERVED_PAYLOAD_KEYS = frozenset(
    {
        "content",
        "chunk_id",
        "document_id",
        "chunk_index",
        "embedding_model",
        "created_at",
        "parent_chunk_id",
        "chunk_offsets",
        "chunk_metadata",
        _META_KEYS,
        "embedding_version",
        "scope",
        "abstract",
        "summary",
        "valid_from",
        "valid_until",
        "entities",
    }
)


def _is_scalar(value: object) -> bool:
    return isinstance(value, (str, int, float, bool)) or value is None


def _metadata_key(key: str) -> str:
    """Payload key a chunk_metadata key is stored under."""
    return f"{_META_PREFIX}{key}"


def _metadata_filters_to_payload(filters: dict[str, Any]) -> dict[str, Any]:
    """Translate a query's ``metadata_filters`` to payload keys.

    Every key is a chunk_metadata key, except ``scope_*`` labels, which are
    kept so a read can narrow by a single label (e.g. under ``ALL_SCOPES``).
    The exact-scope filter is applied after this, so they can't widen a scope.
    """
    return {
        k if k.startswith("scope_") else _metadata_key(k): v for k, v in filters.items()
    }


def _store_filters_to_payload(filters: dict[str, Any]) -> dict[str, Any]:
    """Translate ``find``/``count``/``delete_where`` filters to payload keys.

    Entry-field names, ``scope`` and ``scope_*`` labels are kept as they are;
    every other key is treated as a chunk_metadata key.
    """
    return {
        k
        if k in _RESERVED_PAYLOAD_KEYS or k.startswith("scope_")
        else _metadata_key(k): v
        for k, v in filters.items()
    }


def _decode_chunk_metadata(payload: dict) -> dict:
    """Rebuild ``chunk_metadata`` from the JSON blob and the spread scalars.

    Payloads written before #1186 keep everything in the blob and have no
    ``chunk_meta_keys``. Unprefixed scalars written before #1185 aren't read
    back; re-ingest those entries.
    """
    chunk_metadata = (
        json.loads(payload["chunk_metadata"]) if "chunk_metadata" in payload else {}
    )
    for k in json.loads(payload.get(_META_KEYS, "[]")):
        # Chroma drops None-valued metadata keys on write.
        chunk_metadata[k] = payload.get(_metadata_key(k))
    return chunk_metadata


def _encode_provenance(entry: StoreEntry) -> dict:
    out: dict = {}
    if entry.parent_chunk_id is not None:
        out["parent_chunk_id"] = str(entry.parent_chunk_id)
    if entry.chunk_offsets is not None:
        out["chunk_offsets"] = json.dumps(list(entry.chunk_offsets))
    if entry.chunk_metadata:
        # Scalars are spread (prefixed) so they are filterable; only the rest
        # goes in the JSON blob, so nothing is stored twice.
        scalars = {k: v for k, v in entry.chunk_metadata.items() if _is_scalar(v)}
        rest = {k: v for k, v in entry.chunk_metadata.items() if k not in scalars}
        if scalars:
            out.update({_metadata_key(k): v for k, v in scalars.items()})
            out[_META_KEYS] = json.dumps(list(scalars))
        if rest:
            out["chunk_metadata"] = json.dumps(rest)
    if entry.embedding_version is not None:
        out["embedding_version"] = entry.embedding_version
    return out


def _encode_enrichment(entry: StoreEntry) -> dict:
    out: dict = exact_scope_filter(entry.scope)
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
                # Payloads from before #1746 can carry spread metadata like
                # scope_x=None; skip it rather than fail the whole read.
                if k.startswith("scope_") and isinstance(v, _LABEL_VALUE_TYPES)
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


def _with_scope(
    filters: dict[str, Any], scope: StoreScope | AllScopes | None
) -> dict[str, Any]:
    """Add the exact-scope filter to ``filters``; ``ALL_SCOPES`` adds none.

    ``None`` matches only unscoped entries. The scope is applied last so caller
    filters can't override it.
    """
    if isinstance(scope, AllScopes):
        return dict(filters)
    return {**filters, **exact_scope_filter(scope)}


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

        filters = _with_scope(
            _metadata_filters_to_payload(query.metadata_filters or {}), query.scope
        )

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
        await self._backend.delete_where(exact_scope_filter(scope))

    async def delete_where(self, filters: dict[str, Any]) -> None:
        await self._backend.delete_where(_store_filters_to_payload(filters))

    async def find(self, filters: dict[str, Any], limit: int = 1) -> list[StoreEntry]:
        raw_hits = await self._backend.list_where(
            _store_filters_to_payload(filters), limit
        )
        return [_payload_to_entry(hit_id, payload) for hit_id, payload in raw_hits]

    async def count(self, filters: dict[str, Any] | None = None) -> int:
        return await self._backend.count(_store_filters_to_payload(filters or {}))

    async def nearest_neighbors(
        self,
        embedding: list[float],
        k: int,
        scope: StoreScope | AllScopes | None = None,
    ) -> list[RetrievedStoreEntry]:
        raw_hits = await self._backend.search(embedding, k, _with_scope({}, scope))

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
