"""Retrieval subsystem.

The runtime (:class:`RetrievalRuntime`) orchestrates loading, chunking,
embedding, storage, and retrieval. The :class:`~railtracks.retrieval.stores.Store`
protocol is the storage contract; :class:`~railtracks.retrieval.stores.VectorStore`
is the canonical implementation. The rest of the pipeline is provided
by :mod:`railtracks.retrieval.loaders`, :mod:`railtracks.retrieval.chunking`,
and :mod:`railtracks.retrieval.embedding`.
"""

from .embedding.models import EmbeddingFailure
from .errors import EmbeddingModelMismatchError
from .models import (
    Chunk,
    Document,
    DocumentType,
    EmbeddedChunk,
    RetrievalResult,
    RetrievedChunk,
)
from .runtime import (
    BatchIngested,
    DocumentFailed,
    DocumentSkipped,
    IngestionStats,
    RetrievalRuntime,
)

__all__ = [
    "BatchIngested",
    "Chunk",
    "Document",
    "DocumentFailed",
    "DocumentSkipped",
    "DocumentType",
    "EmbeddedChunk",
    "EmbeddingFailure",
    "EmbeddingModelMismatchError",
    "IngestionStats",
    "RetrievalResult",
    "RetrievalRuntime",
    "RetrievedChunk",
]
