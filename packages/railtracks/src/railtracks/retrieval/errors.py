"""Errors raised by the retrieval runtime."""

from __future__ import annotations


class EmbeddingModelMismatchError(RuntimeError):
    """Raised when the runtime's embedder model differs from the store's.

    Mixing vectors from different embedding models silently produces
    meaningless similarity scores, so the runtime fails loudly before
    issuing the search.
    """
