from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
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
    """Hard-filter namespace for store entries.

    All non-None fields are enforced by stores as mandatory equality filters.
    The scope_ prefix in to_payload_filters() avoids key collisions in flat
    payload dicts that also carry content fields.
    """

    user_id: str | None = None
    agent_id: str | None = None
    session_id: str | None = None
    run_id: str | None = None

    def to_payload_filters(self) -> dict[str, str]:
        return {f"scope_{k}": v for k, v in self.__dict__.items() if v is not None}


class StoreCategory(str, Enum):
    EPISODIC = "episodic"
    SEMANTIC = "semantic"
    SKILL = "skill"
    PROCEDURAL = "procedural"


class RetrievalStrategy(Enum):
    VECTOR = "vector"
    KEYWORD = "keyword"
    GRAPH = "graph"
    TEMPORAL = "temporal"


class DetailLevel(Enum):
    L0 = "abstract"
    L1 = "summary"
    L2 = "full"


@dataclass
class StoreEntry:
    # Required fields
    id: UUID
    content: str
    vector: list[float]
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
    store_category: StoreCategory | None = None
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
        store_category: StoreCategory | None = None,
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
            store_category=store_category,
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
    scope: StoreScope
    embedding: list[float] | None = None
    top_k: int = 10
    strategies: list[RetrievalStrategy] = field(
        default_factory=lambda: [RetrievalStrategy.VECTOR]
    )
    detail_level: DetailLevel = DetailLevel.L2
    store_category: StoreCategory | None = None
    metadata_filters: dict[str, str] | None = None
