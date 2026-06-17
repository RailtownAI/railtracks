from railtracks.retrieval.models import Chunk, Document

from .base import Chunker


class IdentityChunker(Chunker):
    def chunk(self, document: Document) -> list[Chunk]:
        text = document.content
        if not text:
            return []

        pieces = [text]
        offsets = [(0, len(text))]

        return self._make_chunks(
            document, pieces, offsets=offsets
        )
