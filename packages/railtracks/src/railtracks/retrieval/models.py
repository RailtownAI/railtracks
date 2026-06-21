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
    """A unit of source content produced by a loader.

    Attributes:
        content: The decoded textual content of the document. Always a string;
            binary loaders are responsible for their own decoding.
        type: A :class:`DocumentType` describing the content format. Cloud
            loaders infer it from the object's file extension; structured
            loaders (CSV, SQL) set it explicitly.
        id: Unique identifier. If not provided and ``source`` is set, derived
            deterministically from ``source`` via UUID5 (RFC 4122 URL
            namespace) so the same source yields the same id across processes
            — required for the runtime's upsert (``delete_where`` on
            ``document_id``) to find and clear the prior version when content
            changes. Sourceless documents get a random UUID4 (no stable
            identity → no upsert semantics).
        source: The natural identifier of where this document came from —
            a URI (``s3://bucket/key``, ``gs://bucket/name``, ``https://...``),
            a file path, or a relational id. Cloud loaders always set this;
            user-constructed documents may leave it ``None``.

            Writers that derive a storage key (when no ``key_fn`` is supplied)
            look here first; the cloud writers also strip their own URI prefix
            so that "load from S3, write back to S3" produces a clean key
            rather than a nested URI.
        content_hash: SHA-256 of ``content``. Computed by the runtime at
            ingest time; loaders should leave this ``None``. Used by
            staleness-detection to skip re-embedding unchanged documents.
        metadata: Arbitrary provider-specific or user-attached key-value data.
            Loaders use this to expose details like ``bucket``, ``key``,
            ``page``, ``row_index``, etc.
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


@dataclass
class OCRResult:
    """Structured output from an OCR engine.

    Attributes:
        markdown: Full page text as markdown. Tables and headings are
            represented in markdown syntax where the engine supports it.
        bboxes: Bounding-box annotations returned by the engine. Each entry
            is an engine-specific dict; callers should not assume a fixed
            schema across engines.
        tables: Structured table data extracted from the page. Each entry
            is an engine-specific dict representing one table.
    """

    markdown: str
    bboxes: list[dict[str, Any]] = field(default_factory=list)
    tables: list[dict[str, Any]] = field(default_factory=list)

    def to_text(self) -> str:
        return self.markdown
