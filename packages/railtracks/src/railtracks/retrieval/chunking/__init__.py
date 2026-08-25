from typing import TYPE_CHECKING

from .base import Chunker, Splitter
from .fixed_token import FixedTokenChunker, TiktokenTokenizer, Tokenizer
from .identity import IdentityChunker
from .markdown import MarkdownHeaderChunker
from .recursive import RecursiveCharacterChunker, RecursiveSplitter
from .sentence import RegexSentenceSplitter, SentenceChunker

if TYPE_CHECKING:
    from .semantic_chunker import SemanticChunker


__all__ = [
    "Chunker",
    "FixedTokenChunker",
    "IdentityChunker",
    "MarkdownHeaderChunker",
    "RecursiveCharacterChunker",
    "RecursiveSplitter",
    "RegexSentenceSplitter",
    "SemanticChunker",
    "SentenceChunker",
    "Splitter",
    "TiktokenTokenizer",
    "Tokenizer",
]


def __getattr__(name: str):
    if name == "SemanticChunker":
        from .semantic_chunker import SemanticChunker

        return SemanticChunker
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
