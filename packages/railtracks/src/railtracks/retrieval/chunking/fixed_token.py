"""Fixed-size token-window chunker."""

from __future__ import annotations

from ..models import Chunk, Document
from .base import Chunker
from .tokenization import Tokenizer, TiktokenTokenizer


class FixedTokenChunker(Chunker):
    """Splits text into fixed-size token windows with overlap.

    The text is tokenized once via the configured :class:`Tokenizer`, then
    sliced into windows of ``chunk_size`` tokens with ``overlap`` tokens
    of backward overlap between adjacent windows.

    Offset tracking
    ---------------
    Token-based chunkers cannot cheaply recover character offsets from
    tiktoken-style encodings. In current development, this chunker therefore leaves
    :attr:`Chunk.offsets` as ``None``. TODO: add support for this.

    Args:
        chunk_size: Maximum number of tokens per produced chunk.
        overlap: Number of tokens shared between adjacent chunks. Must
            satisfy ``0 <= overlap < chunk_size``.
        tokenizer: Tokenizer implementation to use. Defaults to
            :class:`TiktokenTokenizer` with ``cl100k_base``.
    """

    def __init__(
        self,
        chunk_size: int = 400,
        overlap: int = 200,
        tokenizer: Tokenizer | None = None,
    ) -> None:
        if chunk_size <= 0:
            raise ValueError("'chunk_size' must be greater than 0")
        if overlap < 0:
            raise ValueError("'overlap' must be >= 0")
        if overlap >= chunk_size:
            raise ValueError("'overlap' must be smaller than 'chunk_size'")

        self.chunk_size = chunk_size
        self.overlap = overlap
        self.tokenizer: Tokenizer = tokenizer or TiktokenTokenizer()

    def chunk(self, document: Document) -> list[Chunk]:
        text = document.content
        if not text:
            return []

        tokens = self.tokenizer.encode(text)
        if not tokens:
            return []

        step = self.chunk_size - self.overlap
        pieces: list[str] = []
        start = 0
        while start < len(tokens):
            end = min(start + self.chunk_size, len(tokens))
            pieces.append(self.tokenizer.decode(tokens[start:end]))
            if end == len(tokens):
                break
            start += step

        return self._make_chunks(document, pieces)
