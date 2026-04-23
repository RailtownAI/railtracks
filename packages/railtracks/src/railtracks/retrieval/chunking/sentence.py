"""Sentence-based chunker.

Groups consecutive sentences into chunks of ``chunk_size`` sentences with
``overlap`` sentences of backward overlap between adjacent chunks.

The default sentence boundary detector is a simple regex-based splitter
that handles the common cases (``. ``, ``! ``, ``? ``, line breaks). A
better splitter (e.g. ``pysbd``, ``spaCy``, or an LLM-based one) can be
injected via the :class:`Splitter` protocol without touching this file.

This chunker is deliberately shaped so that sentence-window retrieval
expansion feature can consume its output without a migration. TODO: add support for this.
"""

from __future__ import annotations

import re

from ..models import Chunk, Document
from .base import Chunker, Splitter

# Matches the end of a sentence: ., !, or ? followed by whitespace that
# includes either a space or a newline. We match a lookahead for the
# whitespace so that we can split deterministically and reconstruct the
# original text by concatenation.
_SENTENCE_END_PATTERN = re.compile(r"(?<=[.!?])\s+")


class RegexSentenceSplitter(Splitter):
    """Simple regex-based sentence splitter satisfying the ``Splitter`` protocol.

    Returns a list of sentences; trailing / leading whitespace that was
    previously used as a boundary is dropped. For offset-aware splitting
    used by :class:`SentenceChunker`, see
    :meth:`split_with_positions`.
    """

    def split(self, text: str) -> list[str]:
        return [s for s, _, _ in self.split_with_positions(text)]

    def split_with_positions(self, text: str) -> list[tuple[str, int, int]]:
        """Return ``(sentence, start, end)`` tuples into ``text``.

        Sentences are non-overlapping and ordered; the whitespace between
        sentences is *not* covered by any offset range (so concatenating
        all sentence contents is lossy, but each span slices back to the
        exact sentence text).
        """
        if not text:
            return []

        sentences: list[tuple[str, int, int]] = []
        cursor = 0
        for match in _SENTENCE_END_PATTERN.finditer(text):
            end = match.start()
            if end > cursor:
                sentences.append((text[cursor:end], cursor, end))
            cursor = match.end()
        if cursor < len(text):
            tail = text[cursor:].rstrip()
            if tail:
                sentences.append((tail, cursor, cursor + len(tail)))
        return sentences


class SentenceChunker(Chunker):
    """Groups consecutive sentences into chunks.

    Args:
        chunk_size: Number of sentences per chunk.
        overlap: Number of sentences shared between adjacent chunks.
            Must satisfy ``0 <= overlap < chunk_size``.
        sentence_splitter: Sentence splitter implementing the
            ``Splitter`` protocol. Defaults to
            :class:`RegexSentenceSplitter`. If a custom splitter is
            provided that does not expose ``split_with_positions``,
            offsets are populated by ``str.find`` on the document and
            may be ``None`` for duplicate sentences that cannot be
            located unambiguously.

    Notes:
        Adds ``metadata["sentence_count"]`` (always equal to the number
        of sentences in the chunk) to every produced chunk.
    """

    def __init__(
        self,
        chunk_size: int = 5,
        overlap: int = 1,
        sentence_splitter: Splitter | None = None,
    ) -> None:
        if chunk_size <= 0:
            raise ValueError("'chunk_size' must be greater than 0")
        if overlap < 0:
            raise ValueError("'overlap' must be >= 0")
        if overlap >= chunk_size:
            raise ValueError("'overlap' must be smaller than 'chunk_size'")

        self.chunk_size = chunk_size
        self.overlap = overlap
        self.sentence_splitter: Splitter = sentence_splitter or RegexSentenceSplitter()

    def chunk(self, document: Document) -> list[Chunk]:
        text = document.content
        if not text:
            return []

        sentences = self._split_sentences(text)
        if not sentences:
            return []

        pieces: list[str] = []
        offsets: list[tuple[int, int]] = []
        extra_meta: list[dict] = []

        step = self.chunk_size - self.overlap
        start = 0
        while start < len(sentences):
            end = min(start + self.chunk_size, len(sentences))
            window = sentences[start:end]
            first_start = window[0][1]
            last_end = window[-1][2]
            content = text[first_start:last_end]
            pieces.append(content)
            offsets.append((first_start, last_end))
            extra_meta.append({"sentence_count": len(window)})
            if end == len(sentences):
                break
            start += step

        return self._make_chunks(document, pieces, offsets=offsets, extra_metadata=extra_meta)

    def _split_sentences(self, text: str) -> list[tuple[str, int, int]]:
        """Run the configured splitter and obtain ``(sentence, start, end)`` tuples.

        Prefers an offset-aware ``split_with_positions`` method when the
        splitter exposes one; otherwise falls back to ``str.find`` on the
        document text.
        """
        splitter = self.sentence_splitter
        if hasattr(splitter, "split_with_positions"):
            return splitter.split_with_positions(text)

        out: list[tuple[str, int, int]] = []
        cursor = 0
        for sentence in splitter.split(text):
            if not sentence:
                continue
            idx = text.find(sentence, cursor)
            if idx < 0:
                idx = text.find(sentence)
            if idx < 0:
                # Untraceable sentence (e.g. splitter normalized whitespace);
                # emit with a best-effort cursor-based offset.
                idx = cursor
            end = idx + len(sentence)
            out.append((sentence, idx, end))
            cursor = end
        return out
