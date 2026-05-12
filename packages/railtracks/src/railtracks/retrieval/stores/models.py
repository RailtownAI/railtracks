from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from uuid import UUID


@dataclass(frozen=True)
class Entity:
    name: str
    type: str
    source_chunk_id: UUID
    metadata: dict = field(default_factory=dict)


@dataclass(frozen=True)
class MemoryScope:
    """Hard-filter namespace for memory entries.

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


class MemoryCategory(str, Enum):
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
class MemoryEntry:
    # Required fields
    id: UUID
    content: str
    vector: list[float]
    embedding_model: str
    chunk_id: UUID
    document_id: UUID
    abstract: str
    summary: str
    scope: MemoryScope
    # Optional chunk provenance
    chunk_index: int = 0
    parent_chunk_id: UUID | None = None
    chunk_offsets: tuple[int, int] | None = None
    chunk_metadata: dict = field(default_factory=dict)
    # Optional embedding provenance
    embedding_version: str | None = None
    # Optional memory metadata
    entities: list[Entity] | None = None
    memory_category: MemoryCategory | None = None
    valid_from: datetime | None = None
    valid_until: datetime | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(tz=timezone.utc))


@dataclass
class RetrievedMemoryEntry:
    entry: MemoryEntry
    score: float
    rank: int
    source_retriever: str | None = None
    rerank_score: float | None = None


@dataclass
class MemoryQuery:
    text: str
    scope: MemoryScope
    embedding: list[float] | None = None
    top_k: int = 10
    strategies: list[RetrievalStrategy] = field(
        default_factory=lambda: [RetrievalStrategy.VECTOR]
    )
    detail_level: DetailLevel = DetailLevel.L1
    memory_category: MemoryCategory | None = None
    metadata_filters: dict[str, str] | None = None
