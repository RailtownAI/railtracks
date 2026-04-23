"""Tokenizer abstraction for the retrieval chunking module.

Chunkers remain independent of any specific tokenizer library by depending
on the :class:`Tokenizer` protocol below. ``TiktokenTokenizer`` is the
default concrete implementation; other adapters (HuggingFace,
sentencepiece, ...) live in user code or optional extras.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class Tokenizer(Protocol):
    """Structural protocol for token-count-aware tokenizers.

    Any object exposing ``encode``, ``decode`` and ``count`` with matching
    signatures satisfies the protocol; no inheritance required.
    """

    def encode(self, text: str) -> list[int]: ...

    def decode(self, tokens: list[int]) -> str: ...

    def count(self, text: str) -> int: ...


class TiktokenTokenizer(Tokenizer):
    """Default :class:`Tokenizer` backed by ``tiktoken``.

    Args:
        encoding_name: Name of the ``tiktoken`` encoding to use. Defaults
            to ``cl100k_base`` (GPT-3.5 / GPT-4 family).
    """

    def __init__(self, encoding_name: str = "cl100k_base") -> None:
        import tiktoken  # local import keeps the chunking subsystem importable without tiktoken installed until a tokenizer is actually constructed

        self.encoding_name = encoding_name
        self._encoding = tiktoken.get_encoding(encoding_name)

    def encode(self, text: str) -> list[int]:
        return self._encoding.encode(text)

    def decode(self, tokens: list[int]) -> str:
        return self._encoding.decode(tokens)

    def count(self, text: str) -> int:
        return len(self.encode(text))
