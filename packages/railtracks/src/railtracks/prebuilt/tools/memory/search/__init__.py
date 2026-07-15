"""Ranking algorithms for the prebuilt key-value memory tools.

Lives beside ``KeyValueMemoryToolSet`` as it exists to serve it: each
algorithm ranks the plain ``{key: value}`` snapshot the toolset holds and
returns ``(key, value, score)`` triples.

``LexicalSearch`` (and its config) is pure stdlib and imported eagerly.
``SemanticSearch`` pulls in the embedding + vector stack, so it is loaded
lazily on first access; importing this package for lexical search alone stays
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
