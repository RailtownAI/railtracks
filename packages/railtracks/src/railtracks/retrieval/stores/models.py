from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from uuid import UUID

from railtracks.retrieval.models import EmbeddedChunk


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
    """

    user_id: str | None = None
    agent_id: str | None = None
    session_id: str | None = None
    run_id: str | None = None

    def as_filter_dict(self) -> dict[str, str]:
        return {k: v for k, v in self.__dict__.items() if v is not None}


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
    id: UUID
    chunk: EmbeddedChunk
    abstract: str
    summary: str
    scope: MemoryScope
    entities: list[Entity] | None = None
    memory_category: str | None = None
    valid_from: datetime | None = None
    valid_until: datetime | None = None


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
    filters: dict = field(default_factory=dict)
