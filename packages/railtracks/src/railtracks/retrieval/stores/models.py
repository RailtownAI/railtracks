from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from ..models import EmbeddedChunk


@dataclass(frozen=True)
class Entity:
    name: str
    type: str
    source_chunk_id: UUID
    metadata: dict = field(default_factory=dict)


@dataclass(frozen=True)
class StoreScope:
    """Equality-filter namespace for store entries.

    Each entry in ``labels`` becomes a mandatory equality filter on every
    write and read. The retrieval module is agnostic about what dimensions
    you scope by — pick whichever axes fit your tenancy model::

        StoreScope(labels={"user_id": "alice"})  # SaaS tenancy
        StoreScope(labels={"organization": "acme", "environment": "prod"})  # B2B
        StoreScope(labels={"agent_id": "docs-bot", "session_id": "s1"})  # agent context
        StoreScope(labels={"account_id": 42, "is_prod": True})  # non-string scalars

    The ``scope_`` prefix applied in :meth:`to_payload_filters` avoids key
    collisions in flat payload dicts that also carry content fields.
    """

    labels: Mapping[str, Any] = field(default_factory=dict)

    def to_payload_filters(self) -> dict[str, Any]:
        return {f"scope_{k}": v for k, v in self.labels.items()}


@dataclass
class StoreEntry:
    # Required fields
    id: UUID
    content: str
    vector: list[float] | None
    embedding_model: str
    chunk_id: UUID
    document_id: UUID
    # Optional enrichment fields
    abstract: str | None = None
    summary: str | None = None
    scope: StoreScope | None = None
    # Optional chunk provenance
    chunk_index: int = 0
    parent_chunk_id: UUID | None = None
    chunk_offsets: tuple[int, int] | None = None
    chunk_metadata: dict = field(default_factory=dict)
    # Optional embedding provenance
    embedding_version: str | None = None
    # Optional store metadata
    entities: list[Entity] | None = None
    valid_from: datetime | None = None
    valid_until: datetime | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(tz=timezone.utc))

    @classmethod
    def from_chunk(
        cls,
        embedded_chunk: EmbeddedChunk,
        *,
        scope: StoreScope | None = None,
        abstract: str | None = None,
        summary: str | None = None,
        entities: list[Entity] | None = None,
        valid_from: datetime | None = None,
        valid_until: datetime | None = None,
    ) -> StoreEntry:
        chunk = embedded_chunk.chunk
        return cls(
            id=uuid4(),
            content=chunk.content,
            vector=embedded_chunk.vector,
            embedding_model=embedded_chunk.embedding_model,
            embedding_version=embedded_chunk.embedding_version,
            chunk_id=chunk.id,
            document_id=chunk.document_id,
            chunk_index=chunk.index,
            parent_chunk_id=chunk.parent_chunk_id,
            chunk_offsets=chunk.offsets,
            chunk_metadata=chunk.metadata,
            scope=scope,
            abstract=abstract,
            summary=summary,
            entities=entities,
            valid_from=valid_from,
            valid_until=valid_until,
        )


@dataclass
class RetrievedStoreEntry:
    entry: StoreEntry
    score: float
    rank: int
    source_retriever: str | None = None
    rerank_score: float | None = None


@dataclass
class StoreQuery:
    text: str
    scope: StoreScope | None = None
    embedding: list[float] | None = None
    top_k: int = 10
    metadata_filters: dict[str, Any] | None = None
