from __future__ import annotations

from typing import TYPE_CHECKING

from .key_value import KeyValueMemoryToolSet
from .search import LexicalSearch, LexicalSearchConfig, SearchAlgorithm

if TYPE_CHECKING:
    from .search import SemanticSearch

__all__ = [
    "KeyValueMemoryToolSet",
    "LexicalSearch",
    "LexicalSearchConfig",
    "SearchAlgorithm",
    "SemanticSearch",
]


def __getattr__(name: str):
    # SemanticSearch pulls in the embedding + vector stack; load it lazily so
    # importing the memory tools for lexical search alone stays light.
    if name == "SemanticSearch":
        from .search import SemanticSearch

        return SemanticSearch
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
