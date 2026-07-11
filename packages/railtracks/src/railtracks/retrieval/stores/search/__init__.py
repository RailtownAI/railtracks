"""Ranking algorithms over a ``{key: value}`` snapshot.

A sibling of the ``key_value`` and ``vector`` store packages rather than a
child of either. Search is not a key-value concept — it ranks a plain snapshot
dict — and keeping it here is what lets a semantic ranker depend on the vector
infra without the ``key_value`` package ever importing ``vector``.

``LexicalSearch`` (and its config) is pure stdlib and imported eagerly.
``SemanticSearch`` pulls in the embedding + vector stack, so it is loaded
lazily on first access — importing this package for lexical search alone stays
dependency-light.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from .config import LexicalSearchConfig
from .lexical import LexicalSearch
from .protocol import SearchAlgorithm

if TYPE_CHECKING:
    from .semantic import SemanticSearch

__all__ = [
    "LexicalSearch",
    "LexicalSearchConfig",
    "SearchAlgorithm",
    "SemanticSearch",
]


def __getattr__(name: str):
    if name == "SemanticSearch":
        from .semantic import SemanticSearch

        return SemanticSearch
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
