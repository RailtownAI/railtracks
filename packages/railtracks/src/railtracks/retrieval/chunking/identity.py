"""Identity (whole-document) chunker.

Emits the entire document as a single chunk. Useful as a baseline, for
short documents that should never be split, or as a pass-through stage
in a pipeline that expects chunked input even when no splitting is needed.
"""

from railtracks.retrieval.models import Chunk, Document

from .base import Chunker


class IdentityChunker(Chunker):
    """Chunker that returns the entire document as a single :class:`Chunk`.

    No splitting is performed. The emitted chunk's ``offsets`` span the full
    document (``(0, len(document.content))``), so offset-based slicing still
    works correctly downstream.

    Returns an empty list when ``document.content`` is empty, consistent
    with every other chunker in the suite.

    This is the recommended starting point when:

    * Documents are already short enough that splitting would harm retrieval.
    * You need a ``Chunker``-compatible adapter for a pipeline that expects
      chunks but you want to preserve full-document context.
    * You are writing a baseline experiment to compare against splitting
      strategies.
    """

    def chunk(self, document: Document) -> list[Chunk]:
        """Return the document as a single chunk, or ``[]`` for empty content.

        Args:
            document: Source document to wrap. ``document.id`` and
                ``document.metadata`` propagate onto the produced chunk.

        Returns:
            A list containing exactly one :class:`Chunk` whose ``content``
            equals ``document.content`` and whose ``offsets`` are
            ``(0, len(document.content))``, or an empty list when
            ``document.content`` is falsy.
        """
        text = document.content
        if not text:
            return []

        pieces = [text]
        offsets = [(0, len(text))]

        return self._make_chunks(document, pieces, offsets=offsets)
