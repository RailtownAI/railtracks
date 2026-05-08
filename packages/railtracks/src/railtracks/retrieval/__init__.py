"""Retrieval subsystem.

The runtime (:class:`RetrievalRuntime`) orchestrates loading, chunking,
embedding, storage, and retrieval. The :class:`VectorStore` ABC is the
contract concrete backends implement; the rest of the pipeline is
provided by :mod:`railtracks.retrieval.loaders`,
:mod:`railtracks.retrieval.chunking`, and
:mod:`railtracks.retrieval.embedding`.
"""

from .models import (
    Chunk,
    Cost,
    Document,
    EmbeddedChunk,
    RetrievalResult,
    RetrievedChunk,
)
from .runtime import (
    BatchIngested,
    DocumentFailed,
    EmbeddingModelMismatchError,
    IngestionEvent,
    IngestionStats,
    RetrievalRuntime,
)
from .storage import VectorStore

__all__ = [
    "BatchIngested",
    "Chunk",
    "Cost",
    "Document",
    "DocumentFailed",
    "EmbeddedChunk",
    "EmbeddingModelMismatchError",
    "IngestionEvent",
    "IngestionStats",
    "RetrievalResult",
    "RetrievalRuntime",
    "RetrievedChunk",
    "VectorStore",
]
