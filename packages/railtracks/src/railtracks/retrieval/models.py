from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any
from uuid import UUID, uuid4


class DocumentType(str, Enum):
    TEXT = "text"
    MARKDOWN = "markdown"
    PDF = "pdf"
    CSV = "csv"
    JSON = "json"


@dataclass
class Document:
    """A single piece of source content produced by a loader.

    Attributes:
        content: The raw text content.
        type: Document MIME-ish category. Defaults to TEXT.
        id: Unique identifier, auto-generated as a UUID if not provided.
        source: Origin of the content — file path, URL, database key, etc.
        content_hash: SHA-256 of ``content``. Computed by the runtime at
            ingest time; loaders should leave this ``None``. Used by
            staleness-detection to skip re-embedding unchanged documents.
        metadata: Arbitrary key-value pairs attached by the loader (page number,
            language, author, etc.).
    """

    content: str
    type: DocumentType = DocumentType.TEXT
    id: UUID = field(default_factory=uuid4)
    source: str | None = None
    content_hash: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class Chunk:
    content: str
    document_id: UUID
    id: UUID = field(default_factory=uuid4)
    index: int = 0
    parent_chunk_id: UUID | None = None
    offsets: tuple[int, int] | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


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
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Cost:
    tokens: int | None = None
    latency_ms: float | None = None
    dollars: float | None = None
