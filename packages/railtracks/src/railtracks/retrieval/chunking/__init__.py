"""Chunking subsystem public surface.

The module provides four concrete ``Chunker`` implementations plus the
small set of abstractions they are built on (``Tokenizer``,
``Splitter``, ``Chunker`` ABC). It is intentionally not re-exported at
the top-level ``railtracks`` namespace in development; the module becomes
user-facing once the retriever node lands.

Usage
-----

Start from a :class:`~railtracks.retrieval.Document`:

.. code-block:: python

    from railtracks.retrieval import Document
    from railtracks.retrieval.chunking import (
        FixedTokenChunker,
        MarkdownHeaderChunker,
        RecursiveCharacterChunker,
        SentenceChunker,
    )

    doc = Document(
        content=open("notes.md").read(),
        type="markdown",
        source="notes.md",
        metadata={"lang": "en"},
    )

    # Recommended default for most plain-text corpora
    chunks = RecursiveCharacterChunker(chunk_size=800, overlap=100).chunk(doc)

    # Token-window style (offsets not tracked in v1, TODO: add support for this)
    chunks = FixedTokenChunker(chunk_size=400, overlap=50).chunk(doc)

    # Group consecutive sentences (good for sentence-window retrieval)
    chunks = SentenceChunker(chunk_size=5, overlap=1).chunk(doc)

    # Structured Markdown with heading breadcrumbs in metadata
    chunks = MarkdownHeaderChunker(chunk_size=1000).chunk(doc)

All chunkers produce :class:`~railtracks.retrieval.Chunk` objects that
are storage-backend-agnostic: the same output feeds vector stores, BM25
indexes, graph stores, or plain SQL archives. Embedding vectors live on
:class:`~railtracks.retrieval.EmbeddedChunk`, never on ``Chunk``.

Writing a custom chunker
------------------------

Subclass :class:`Chunker` and implement ``chunk(document)``. Assemble
output exclusively via the protected ``_make_chunks`` helper, which is
where every invariant lives (``document_id`` propagation, dense 0-based
``index``, metadata inheritance, offset copy-through):

.. code-block:: python

    from railtracks.retrieval import Chunk, Document
    from railtracks.retrieval.chunking import Chunker


    class ParagraphChunker(Chunker):
        def chunk(self, document: Document) -> list[Chunk]:
            pieces: list[str] = []
            offsets: list[tuple[int, int]] = []
            cursor = 0
            for piece in document.content.split("\\n\\n"):
                start = document.content.find(piece, cursor)
                end = start + len(piece)
                pieces.append(piece)
                offsets.append((start, end))
                cursor = end
            return self._make_chunks(document, pieces, offsets=offsets)

Limitations
-----------

* Token-based chunkers (``FixedTokenChunker``) leave
  ``Chunk.offsets`` as ``None`` in v1. Recovering accurate character
  offsets requires tokenizer-specific support (e.g. HuggingFace offset
  mappings) that is out of scope for the first pass.
"""

from .base import Chunker, Splitter
from .fixed_token import FixedTokenChunker
from .markdown import MarkdownHeaderChunker
from .recursive import RecursiveCharacterChunker, RecursiveSplitter
from .sentence import RegexSentenceSplitter, SentenceChunker
from .tokenization import TiktokenTokenizer, Tokenizer

__all__ = [
    "Chunker",
    "FixedTokenChunker",
    "MarkdownHeaderChunker",
    "RecursiveCharacterChunker",
    "RecursiveSplitter",
    "RegexSentenceSplitter",
    "SentenceChunker",
    "Splitter",
    "TiktokenTokenizer",
    "Tokenizer",
]
