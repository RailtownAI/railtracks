from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any
from uuid import NAMESPACE_URL, UUID, uuid4, uuid5

# Sentinel "no id supplied" marker — the RFC 4122 nil UUID, which is never
# legitimately used as an entity id. If you ever need to distinguish "the
# nil UUID" from "no id supplied" we'd need a different sentinel.
_UNSET_DOCUMENT_ID = UUID(int=0)


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
        id: Unique identifier. If not provided and ``source`` is set, derived
            deterministically from ``source`` via UUID5 (RFC 4122 URL
            namespace) so the same source yields the same id across processes
            — required for the runtime's upsert (``delete_where`` on
            ``document_id``) to find and clear the prior version when content
            changes. Sourceless documents get a random UUID4 (no stable
            identity → no upsert semantics).
        source: Origin of the content — file path, URL, database key, etc.
        content_hash: SHA-256 of ``content``. Computed by the runtime at
            ingest time; loaders should leave this ``None``. Used by
            staleness-detection to skip re-embedding unchanged documents.
        metadata: Arbitrary key-value pairs attached by the loader (page number,
            language, author, etc.).
    """

    content: str
    type: DocumentType = DocumentType.TEXT
    id: UUID = _UNSET_DOCUMENT_ID
    source: str | None = None
    content_hash: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.id == _UNSET_DOCUMENT_ID:
            self.id = (
                uuid5(NAMESPACE_URL, self.source)
                if self.source is not None
                else uuid4()
            )


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
