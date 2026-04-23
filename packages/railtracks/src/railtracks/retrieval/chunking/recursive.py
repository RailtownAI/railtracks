"""Recursive character-based chunker.

Tries separators in priority order (paragraphs, lines, sentences, words,
characters) until every piece fits under ``chunk_size``, then merges
adjacent pieces back into chunks of the configured size with overlap.

This is the recommended general-purpose default for most text corpora.
"""

from __future__ import annotations

from typing import Callable

from ..models import Chunk, Document
from .base import Chunker

DEFAULT_SEPARATORS: list[str] = ["\n\n", "\n", ". ", " ", ""]


class RecursiveSplitter:
    """Reusable recursive character splitter.

    Implements the ``Splitter`` protocol (``split(text) -> list[str]``) so
    other chunkers (e.g. :class:`MarkdownHeaderChunker`) can compose it as
    a fallback. When offsets are needed, use
    :meth:`split_with_positions` directly.

    Args:
        chunk_size: Target maximum size per atomic piece, measured via
            ``length_fn``. Used both during recursion (to decide when a
            piece is small enough to stop splitting) and during merging.
        overlap: Number of units (per ``length_fn``) shared between
            adjacent merged chunks.
        separators: Ordered separators to try, from coarsest to finest.
            The last separator should generally be ``""`` to guarantee
            termination by character-level splitting.
        length_fn: Function used to measure piece / chunk length.
            Defaults to :func:`len` (character count). Pass
            ``tokenizer.count`` to size by tokens.
    """

    def __init__(
        self,
        chunk_size: int = 1000,
        overlap: int = 200,
        separators: list[str] | None = None,
        length_fn: Callable[[str], int] | None = None,
    ) -> None:
        if chunk_size <= 0:
            raise ValueError("'chunk_size' must be greater than 0")
        if overlap < 0:
            raise ValueError("'overlap' must be >= 0")
        if overlap >= chunk_size:
            raise ValueError("'overlap' must be smaller than 'chunk_size'")

        self.chunk_size = chunk_size
        self.overlap = overlap
        self.separators = list(separators) if separators is not None else list(DEFAULT_SEPARATORS)
        self.length_fn: Callable[[str], int] = length_fn or len

    # ------------------------------------------------------------------
    # Splitter protocol
    # ------------------------------------------------------------------

    def split(self, text: str) -> list[str]:
        """Split ``text`` into merged pieces of size ~``chunk_size``."""
        return [p for p, _, _ in self.split_with_positions(text)]

    # ------------------------------------------------------------------
    # Offset-aware split used by RecursiveCharacterChunker
    # ------------------------------------------------------------------

    def split_with_positions(self, text: str) -> list[tuple[str, int, int]]:
        """Split ``text`` and return ``(piece, start, end)`` for each chunk.

        Offsets are absolute indices into ``text``.
        """
        if not text:
            return []
        atoms = self._recursive_split(text, 0, self.separators)
        return self._merge(atoms)

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _recursive_split(
        self,
        text: str,
        base_offset: int,
        separators: list[str],
    ) -> list[tuple[str, int, int]]:
        """Recursively split ``text`` into atomic pieces each under ``chunk_size``.

        Pieces returned always cover ``text`` contiguously: concatenating
        their ``content`` in order yields back ``text`` exactly. This is
        what makes offset bookkeeping trivial for the merger.
        """
        # Pick the coarsest separator that actually occurs in `text`;
        # if none match, fall back to the last (typically "").
        chosen_idx = len(separators) - 1
        for i, sep in enumerate(separators):
            if sep == "" or sep in text:
                chosen_idx = i
                break
        separator = separators[chosen_idx]
        remaining = separators[chosen_idx + 1 :]

        pieces = _split_keeping_separator(text, base_offset, separator)

        results: list[tuple[str, int, int]] = []
        for piece, pstart, pend in pieces:
            if self.length_fn(piece) <= self.chunk_size:
                results.append((piece, pstart, pend))
                continue
            if remaining:
                results.extend(self._recursive_split(piece, pstart, remaining))
            else:
                # Hard fallback: chop by length_fn == len (character) slices
                # of exactly chunk_size. We only reach this for custom
                # length_fn that rates very short strings as too long.
                results.extend(_hard_chop(piece, pstart, self.chunk_size))
        return results

    def _merge(
        self,
        atoms: list[tuple[str, int, int]],
    ) -> list[tuple[str, int, int]]:
        """Greedy merge of atomic pieces into chunks of ~``chunk_size`` with overlap."""
        if not atoms:
            return []

        chunks: list[tuple[str, int, int]] = []
        buffer: list[tuple[str, int, int]] = []
        buffer_len = 0

        for piece, pstart, pend in atoms:
            piece_len = self.length_fn(piece)
            # If even a single atom exceeds chunk_size, emit it as its own
            # chunk; we already did our best in _recursive_split.
            if piece_len > self.chunk_size and not buffer:
                chunks.append((piece, pstart, pend))
                continue

            if buffer and buffer_len + piece_len > self.chunk_size:
                chunks.append(_join_span(buffer))
                # shrink buffer from the front until it fits both the
                # overlap budget and the incoming piece
                while buffer and (
                    buffer_len > self.overlap
                    or (buffer and buffer_len + piece_len > self.chunk_size)
                ):
                    removed = buffer.pop(0)
                    buffer_len -= self.length_fn(removed[0])
                    if not buffer:
                        break

            buffer.append((piece, pstart, pend))
            buffer_len += piece_len

        if buffer:
            chunks.append(_join_span(buffer))

        return chunks


class RecursiveCharacterChunker(Chunker):
    """Chunker built on :class:`RecursiveSplitter`.

    Populates ``Chunk.offsets`` with accurate character offsets into
    ``Document.content``.

    Args:
        chunk_size: Target maximum size per chunk, measured via
            ``length_fn``.
        overlap: Shared units (per ``length_fn``) between adjacent
            chunks.
        separators: Ordered separators; see :class:`RecursiveSplitter`.
        length_fn: Length measure; defaults to ``len``. Pass
            ``tokenizer.count`` to size by tokens.
    """

    def __init__(
        self,
        chunk_size: int = 1000,
        overlap: int = 200,
        separators: list[str] | None = None,
        length_fn: Callable[[str], int] | None = None,
    ) -> None:
        self.splitter = RecursiveSplitter(
            chunk_size=chunk_size,
            overlap=overlap,
            separators=separators,
            length_fn=length_fn,
        )

    @property
    def chunk_size(self) -> int:
        return self.splitter.chunk_size

    @property
    def overlap(self) -> int:
        return self.splitter.overlap

    def chunk(self, document: Document) -> list[Chunk]:
        if not document.content:
            return []

        pieces_with_positions = self.splitter.split_with_positions(document.content)
        if not pieces_with_positions:
            return []

        pieces = [p for p, _, _ in pieces_with_positions]
        offsets = [(s, e) for _, s, e in pieces_with_positions]
        return self._make_chunks(document, pieces, offsets=offsets)


# ---------------------------------------------------------------------------
# Module-level helpers (kept private so we can reuse them from tests if needed)
# ---------------------------------------------------------------------------


def _split_keeping_separator(
    text: str,
    base_offset: int,
    separator: str,
) -> list[tuple[str, int, int]]:
    """Split ``text`` at ``separator`` keeping the separator attached to
    the preceding piece. The produced pieces concatenate back to ``text``
    exactly, which makes offset bookkeeping trivial.

    When ``separator`` is the empty string, returns one atom per
    character.
    """
    if not text:
        return []

    if separator == "":
        return [(ch, base_offset + i, base_offset + i + 1) for i, ch in enumerate(text)]

    pieces: list[tuple[str, int, int]] = []
    start = 0
    sep_len = len(separator)
    while True:
        idx = text.find(separator, start)
        if idx < 0:
            if start < len(text):
                pieces.append((text[start:], base_offset + start, base_offset + len(text)))
            break
        end = idx + sep_len
        pieces.append((text[start:end], base_offset + start, base_offset + end))
        start = end
        if start == len(text):
            break
    return pieces


def _hard_chop(text: str, base_offset: int, chunk_size: int) -> list[tuple[str, int, int]]:
    """Character-level fallback used only when no separator remains and a
    piece is still too large under a custom ``length_fn``.
    """
    if not text:
        return []
    out: list[tuple[str, int, int]] = []
    for i in range(0, len(text), chunk_size):
        segment = text[i : i + chunk_size]
        out.append((segment, base_offset + i, base_offset + i + len(segment)))
    return out


def _join_span(buffer: list[tuple[str, int, int]]) -> tuple[str, int, int]:
    """Join a non-empty buffer of contiguous pieces into one span."""
    content = "".join(p for p, _, _ in buffer)
    start = buffer[0][1]
    end = buffer[-1][2]
    return content, start, end
