from __future__ import annotations

from uuid import UUID, uuid4
from dataclasses import dataclass, field
from typing import Any



@dataclass
class Document:
    """A single piece of source content produced by a loader.

    Attributes:
        content: The raw text content.
        id: Unique identifier, auto-generated as a UUID if not provided.
        source: Origin of the content — file path, URL, database key, etc.
        metadata: Arbitrary key-value pairs attached by the loader (page number,
            language, author, etc.).
    """

    content: str
    type: str
    id: UUID = field(default_factory=uuid4)
    source: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class Chunk:
    """A chunk of a :class:`Document`, produced by a ``Chunker``.

    ``Chunk`` is intentionally storage-backend-agnostic. The same chunker
    output is consumed by vector stores, BM25 indexes, graph stores, or
    plain SQL archives. Embedding vectors are stored on
    :class:`EmbeddedChunk`, never here.

    Attributes:
        content: Chunk text.
        document_id: UUID of the source :class:`Document`.
        id: Stable identifier for this chunk.
        index: Dense, 0-based position within the parent document
            (``0, 1, 2, ...``).
        parent_chunk_id: For hierarchical / auto-merging retrieval, the
            coarser chunk this one was derived from.
        offsets: ``(start, end)`` character offsets into
            ``Document.content`` for this chunk. Optional; some chunkers
            (notably token-based ones) cannot populate it and leave
            it ``None``.
        metadata: Arbitrary key-value metadata. Inherited as a shallow
            copy from the source ``Document`` and then extended by the
            chunker.
    """

    content: str
    document_id: UUID
    id: UUID = field(default_factory=uuid4)
    index: int = 0
    parent_chunk_id: UUID | None = None
    offsets: tuple[int, int] | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class EmbeddedChunk:
    """A :class:`Chunk` plus its embedding vector.

    Produced by an ``Embedder``; consumed by a ``VectorStore``.
    """

    chunk: Chunk
    vector: list[float]
    embedding_model: str
    embedding_version: str | None = None  # for safe embedding migrations


@dataclass
class RetrievedChunk:
    """A :class:`Chunk` returned from a retriever, annotated with search
    signals.
    """

    chunk: Chunk
    score: float
    rank: int  # 0-based position in the retrieved set
    source_retriever: str | None = None  # e.g. "dense", "bm25"
    rerank_score: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class RetrievalResult:
    """The output of a retriever call."""

    query: str
    chunks: list[RetrievedChunk]
    total_candidates: int | None = None  # considered before top_k selection
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class CostBudget:
    """Declarative budget threaded through retrieval."""

    tokens: int | None = None  # retrieved token cap
    latency_ms: float | None = None  # soft target
    dollars: float | None = None  # hard ceiling
