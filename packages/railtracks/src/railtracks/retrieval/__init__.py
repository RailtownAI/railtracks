"""Retrieval subsystem (chunking).

Only the domain models are exported at the package level today. The
chunking API is accessed via ``railtracks.retrieval.chunking`` until the
full retrieval pipeline (embedding, vector store, retriever node) lands
and the module becomes user-facing.
"""

from .models import (
    Chunk,
    CostBudget,
    Document,
    EmbeddedChunk,
    RetrievalResult,
    RetrievedChunk,
)

__all__ = [
    "Chunk",
    "CostBudget",
    "Document",
    "EmbeddedChunk",
    "RetrievalResult",
    "RetrievedChunk",
]
