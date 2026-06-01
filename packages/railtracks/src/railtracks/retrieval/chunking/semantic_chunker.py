"""Semantic chunker.

Splits a document at topic boundaries by embedding consecutive text units
(typically sentences), measuring cosine distance between neighbors, and
merging units wherever the distance exceeds a percentile-based threshold.

Requires ``scikit-learn`` (and ``numpy``) — install via
``pip install 'railtracks[rag]'``.
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
    """Chunk a document at semantically coherent boundaries.

    Pipeline:

    1. Split ``document.content`` into units via ``sentence_splitter``.
    2. Optionally wrap each unit with neighboring text for richer embeddings
       (``combine_neighbors``).
    3. Embed units with the configured :class:`~railtracks.retrieval.embedding.base.Embedding`.
    4. Compute cosine **distance** (``1 - similarity``) between each adjacent
       pair of embeddings.
    5. Flag breakpoints where distance exceeds the
       ``threshold_percentile`` of all distances in the document.
    6. Merge units between breakpoints and return :class:`Chunk` objects via
       :meth:`_make_chunks`.

    Args:
        embedder: Embedding provider. :meth:`chunk` calls
            ``embedder.embed(...)`` synchronously; do not invoke from inside
            a running async event loop.
        sentence_splitter: Unit splitter implementing the ``Splitter`` protocol.
            Defaults to :class:`RegexSentenceSplitter`.
        threshold_percentile: Percentile (0–100) of pairwise distances used
            as the split threshold. Higher values produce fewer, larger
            chunks (only the largest semantic jumps split). Common default:
            ``95.0``.
        combine_neighbors: When ``True``, each unit sent to the embedder
            includes up to ``window`` neighbors on each side. When ``False``,
            units are embedded exactly as split.
        window: Neighbor radius used only when ``combine_neighbors`` is
            ``True``.

    Notes:
        Produced :class:`Chunk` objects inherit ``document.metadata`` but do
        not currently populate :attr:`~railtracks.retrieval.models.Chunk.offsets`.
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

        Args:
            document: Source document whose ``content`` is split and embedded.

        Returns:
            Ordered :class:`Chunk` list with dense 0-based ``index`` values.
            Returns ``[]`` when ``document.content`` is empty.
        """
        if not document.content:
            return []

        split_texts = self.sentence_splitter.split(document.content)
        texts_to_embed = self._prepare_embed_inputs(split_texts)
        embeddings = self.embedder.embed(texts_to_embed).vectors
        distances = self._calculate_distances(embeddings)
        breakpoints = self._identify_breakpoints(distances, self.threshold_percentile)
        pieces = self._create_chunks(split_texts, breakpoints)
        return self._make_chunks(document, pieces)

    def _calculate_distances(self, embeddings: list[list[float]]) -> list[float]:
        """Compute cosine distance between each consecutive embedding pair.

        Args:
            embeddings: One vector per text unit, in document order.

        Returns:
            ``distances[i]`` is ``1 - cosine_similarity(embeddings[i],
            embeddings[i + 1])``. Empty when fewer than two embeddings are
            provided.
        """
        if len(embeddings) < 2:
            return []
        distances: list[float] = []
        for i in range(len(embeddings) - 1):
            similarity = cosine_similarity([embeddings[i]], [embeddings[i + 1]])[0][0]
            distances.append(1.0 - similarity)
        return distances

    def _identify_breakpoints(
        self, distances: list[float], threshold_percentile: float
    ) -> list[int]:
        """Return indices where semantic distance exceeds a percentile threshold.

        Args:
            distances: Pairwise distances from :meth:`_calculate_distances`.
            threshold_percentile: Percentile passed to ``numpy.percentile``.

        Returns:
            Sorted indices ``i`` where ``distances[i] > threshold``. Index
            ``i`` marks a break **after** unit ``i`` and before unit ``i + 1``.
            Empty when ``distances`` is empty.

        Example:
            Given ``distances = [0.1, 0.12, 0.11, 0.85, 0.13]`` and
            ``threshold_percentile = 95``::

                threshold = np.percentile(distances, 95)  # ~0.79
                # 0.85 > 0.79  →  breakpoint at index 3 (split after unit 3)

            Only the unusually large gap (the topic shift at index 3) exceeds
            the 95th-percentile cutoff; smaller, typical distances do not.
        """
        if not distances:
            return []
        threshold = np.percentile(distances, threshold_percentile)
        return [i for i, dist in enumerate(distances) if dist > threshold]

    def _create_chunks(self, sentences: list[str], breakpoints: list[int]) -> list[str]:
        """Merge split units into chunk strings at the given breakpoints.

        Args:
            sentences: Ordered unit texts (e.g. sentences).
            breakpoints: Indices from :meth:`_identify_breakpoints`. Each
                index ends the current chunk and starts the next after it.

        Returns:
            Chunk text strings joined with spaces. Returns ``[]`` when
            ``sentences`` is empty.
        """
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
        """Select texts to send to the embedder for each unit.

        Args:
            sentences: Ordered unit texts from the sentence splitter.

        Returns:
            Either ``sentences`` unchanged, or contextualized strings from
            :meth:`_add_context` when ``combine_neighbors`` is enabled.
        """
        if not self.combine_neighbors:
            return sentences
        return self._add_context(sentences, self.window)

    def _add_context(self, sentences: list[str], window_size: int) -> list[str]:
        """Build a local context window around each sentence for embedding.

        Args:
            sentences: Ordered unit texts.
            window_size: Number of neighbors to include on each side of the
                center sentence.

        Returns:
            One string per input sentence. Entry ``i`` joins
            ``sentences[max(0, i - window_size) : min(n, i + window_size + 1)]``
            with spaces.
        """
        contextualized: list[str] = []
        for i in range(len(sentences)):
            start = max(0, i - window_size)
            end = min(len(sentences), i + window_size + 1)
            contextualized.append(" ".join(sentences[start:end]))
        return contextualized
