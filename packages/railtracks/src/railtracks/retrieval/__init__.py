"""Retrieval subsystem (chunking).

Only the domain models are exported at the package level today. The
chunking API is accessed via ``railtracks.retrieval.chunking`` until the
full retrieval pipeline (embedding, vector store, retriever node) lands
and the module becomes user-facing.
"""

from .models import (
    Chunk,
    Cost,
    Document,
    EmbeddedChunk,
    RetrievalResult,
    RetrievedChunk,
)

__all__ = [
    "Chunk",
    "Cost",
    "Document",
    "EmbeddedChunk",
    "RetrievalResult",
    "RetrievedChunk",
]
