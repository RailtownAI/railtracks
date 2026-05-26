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
    """A unit of source content produced by a loader.

    Attributes:
        content: The decoded textual content of the document. Always a string;
            binary loaders are responsible for their own decoding.
        type: A :class:`DocumentType` describing the content format. Cloud
            loaders infer it from the object's file extension; structured
            loaders (CSV, SQL) set it explicitly.
        id: An auto-generated :class:`uuid.UUID` identifying this instance
            **in memory**. Stable for the lifetime of the object but not
            persisted by any loader — re-loading the same source produces a
            different ``id``. Treat as a process-local handle, not a primary
            key.
        source: The natural identifier of where this document came from —
            a URI (``s3://bucket/key``, ``gs://bucket/name``, ``https://...``),
            a file path, or a relational id. Cloud loaders always set this;
            user-constructed documents may leave it ``None``.

            Writers that derive a storage key (when no ``key_fn`` is supplied)
            look here first; the cloud writers also strip their own URI prefix
            so that "load from S3, write back to S3" produces a clean key
            rather than a nested URI.
        metadata: Arbitrary provider-specific or user-attached key-value data.
            Loaders use this to expose details like ``bucket``, ``key``,
            ``page``, ``row_index``, etc.
    """

    content: str
    type: DocumentType
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
    tokens: int | None = None
    latency_ms: float | None = None
    dollars: float | None = None
