"""Semantic chunker template.

Subclass of :class:`Chunker` for embedding-driven boundary detection.
Implement :meth:`chunk` (and any helpers you need) to complete this chunker.
"""

from __future__ import annotations

import numpy as np
from sklearn.metrics.pairwise import cosine_similarity

from railtracks.utils.logging.create import get_rt_logger

from ..embedding.base import Embedding
from ..models import Chunk, Document
from .base import Chunker, Splitter
from .sentence import RegexSentenceSplitter

logger = get_rt_logger(__name__)


class SemanticChunker(Chunker):
    """Template for semantic chunking via embedding similarity.

    Args:
        embedder: An :class:`~railtracks.retrieval.embedding.base.Embedding`
            instance used to vectorize text units during chunking.
        sentence_splitter: Unit splitter implementing the ``Splitter`` protocol.
            Defaults to :class:`RegexSentenceSplitter`.
        threshold_percentile: Percentile of consecutive embedding distances
            used as the breakpoint threshold. Distances above this value
            start a new chunk.
        combine_neighbors: When ``True``, each unit is embedded together with
            neighboring units (see ``window``). When ``False``, units are
            embedded as split with no neighbor merging.
        window: Number of neighboring sentences to include on each side when
            ``combine_neighbors`` is ``True``. Ignored otherwise.
    """

    def __init__(
        self,
        embedder: Embedding,
        sentence_splitter: Splitter | None = None,
        *,
        threshold_percentile: float = 95.0,
        combine_neighbors: bool = False,
        window: int = 1,
    ) -> None:
        if not 0.0 <= threshold_percentile <= 100.0:
            raise ValueError("'threshold_percentile' must be between 0 and 100")
        if window < 0:
            raise ValueError("'window' must be >= 0")

        self.embedder = embedder
        self.sentence_splitter = sentence_splitter or RegexSentenceSplitter()
        self.threshold_percentile = threshold_percentile
        self.combine_neighbors = combine_neighbors
        self.window = window
        logger.debug(
            "SemanticChunker initialized (embedder=%s, splitter=%s, "
            "threshold_percentile=%s, combine_neighbors=%s, window=%s)",
            type(embedder).__name__,
            type(self.sentence_splitter).__name__,
            threshold_percentile,
            combine_neighbors,
            window,
        )

    def chunk(self, document: Document) -> list[Chunk]:
        """Split *document* into semantically coherent chunks.

        Suggested flow (implement as you prefer):

        1. Split ``document.content`` into units (e.g. sentences).
        2. Optionally build contextualized unit texts when
           ``combine_neighbors`` is enabled.
        3. Embed unit texts with ``self.embedder.embed(...)``.
        4. Compare adjacent embeddings; pick breakpoints where similarity drops.
        5. Merge units between breakpoints into chunk strings + offsets.
        6. Return ``self._make_chunks(document, pieces, offsets=offsets)``.
        """
        if not document.content:
            return []

        split_texts = self.sentence_splitter.split(document.content)
        texts_to_embed = self._prepare_embed_inputs(split_texts)
        embeddings = self.embedder.embed(texts_to_embed).vectors
        distances = self._calculate_distances(embeddings)
        breakpoints = self._identify_breakpoints(
            distances, self.threshold_percentile
        )
        pieces = self._create_chunks(split_texts, breakpoints)
        return self._make_chunks(document, pieces)

    def _calculate_distances(
        self, embeddings: list[list[float]]
    ) -> list[float]:
        """Calculate cosine distances between consecutive embeddings."""
        if len(embeddings) < 2:
            return []
        distances: list[float] = []
        for i in range(len(embeddings) - 1):
            similarity = cosine_similarity(
                [embeddings[i]], [embeddings[i + 1]]
            )[0][0]
            distances.append(1.0 - similarity)
        return distances

    def _identify_breakpoints(
        self, distances: list[float], threshold_percentile: float
    ) -> list[int]:
        """Find natural breaking points in the text based on semantic distances."""
        if not distances:
            return []
        threshold = np.percentile(distances, threshold_percentile)
        return [i for i, dist in enumerate(distances) if dist > threshold]

    def _create_chunks(
        self, sentences: list[str], breakpoints: list[int]
    ) -> list[str]:
        """Create initial text chunks based on identified breakpoints."""
        if not sentences:
            return []

        chunks: list[str] = []
        start_idx = 0

        for breakpoint in breakpoints:
            chunks.append(" ".join(sentences[start_idx : breakpoint + 1]))
            start_idx = breakpoint + 1

        chunks.append(" ".join(sentences[start_idx:]))
        return chunks

    def _prepare_embed_inputs(self, sentences: list[str]) -> list[str]:
        """Return texts to embed, optionally with neighboring sentence context."""
        if not self.combine_neighbors:
            return sentences
        return self._add_context(sentences, self.window)

    def _add_context(
        self, sentences: list[str], window_size: int
    ) -> list[str]:
        """Combine each sentence with neighboring sentences for embedding context."""
        contextualized: list[str] = []
        for i in range(len(sentences)):
            start = max(0, i - window_size)
            end = min(len(sentences), i + window_size + 1)
            contextualized.append(" ".join(sentences[start:end]))
        return contextualized
