from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from uuid import UUID, uuid4


class DocumentType(str, Enum):
    TEXT = "text"
    MARKDOWN = "markdown"
    PDF = "pdf"
    CSV = "csv"
    JSON = "json"


@dataclass
class Document:
    content: str
    type: str
    id: UUID = field(default_factory=uuid4)
    source: str | None = None
    metadata: dict = field(default_factory=dict)


@dataclass
class Chunk:
    content: str
    document_id: UUID
    id: UUID = field(default_factory=uuid4)
    index: int = 0
    parent_chunk_id: UUID | None = None
    offsets: tuple[int, int] | None = None
    metadata: dict = field(default_factory=dict)


@dataclass
class EmbeddedChunk:
    chunk: Chunk
    vector: list[float]
    embedding_model: str
    embedding_version: str | None = None


@dataclass
class RetrievedChunk:
    chunk: Chunk
    score: float
    rank: int
    source_retriever: str | None = None
    rerank_score: float | None = None


@dataclass
class RetrievalResult:
    query: str
    chunks: list[RetrievedChunk]
    total_candidates: int | None = None
    metadata: dict = field(default_factory=dict)


@dataclass(frozen=True)
class Cost:
    tokens: int
