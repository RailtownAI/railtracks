"""Semantic chunker template.

Subclass of :class:`Chunker` for embedding-driven boundary detection.
Implement :meth:`chunk` (and any helpers you need) to complete this chunker.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from ..models import Chunk, Document
from .base import Chunker, Splitter


class SemanticChunker(Chunker):
    """Template for semantic chunking via embedding similarity.

    Args:
        embed_fn: Synchronous ``(texts) -> list[list[float]]``. Wire a local
            model or ``Embedding.embed()`` when not in an async context.
        **kwargs: Optional config (thresholds, splitters, size limits, etc.).
            Store whatever you need on ``self`` in :meth:`__init__`.
    """

    def __init__(
        self,
        embed_fn: Callable[[list[str]], list[list[float]]],
        sentence_splitter: Splitter,
        **kwargs: Any,
    ) -> None:
        self.embed_fn = embed_fn
        for key, value in kwargs.items():
            setattr(self, key, value)

    def chunk(self, document: Document) -> list[Chunk]:
        """Split *document* into semantically coherent chunks.

        Suggested flow (implement as you prefer):

        1. Split ``document.content`` into units (e.g. sentences).
        2. Embed unit texts with ``self.embed_fn``.
        3. Compare adjacent embeddings; pick breakpoints where similarity drops.
        4. Merge units between breakpoints into chunk strings + offsets.
        5. Return ``self._make_chunks(document, pieces, offsets=offsets)``.
        """
        if not document.content:
            return []

        raise NotImplementedError(
            "SemanticChunker.chunk is not implemented yet"
        )
