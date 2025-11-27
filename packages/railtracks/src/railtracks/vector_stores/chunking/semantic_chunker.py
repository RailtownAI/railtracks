from typing import Optional

import tiktoken

from .base_chunker import BaseChunker


class SentenceChunker(BaseChunker):
    """A chunker that splits text by sentences given a chunking size target.

    This implementation divides text using a text window as guide for chunk
    size but ensuring to split on semantically imortant characters optionally
    with overlap between chunks. Tokenization is performed using `tiktoken`
    and defaults to the `cl100k_base` tokenizer unless otherwise specified.

    Args:
        chunk_size (int): Goal for number of tokens in a produced chunk.
            Defaults to 400.
        overlap (int): Number of tokens shared between adjacent chunks.
            Defaults to 200.
        tokenizer (Optional[str]): Name of the `tiktoken` encoding to use. If
            omitted, ``cl100k_base`` is used.

    Attributes:
        _chunk_size (int): Internal storage for chunk size.
        _overlap (int): Internal storage for token overlap.
        _tokenizer (tiktoken.Encoding): Tokenizer used for encoding/decoding.
    """

    def __init__(
        self, chunk_size: int = 400, overlap: int = 200, tokenizer: Optional[str] = None
    ):
        super().__init__(chunk_size, overlap)
        self._tokenizer = (
            tiktoken.get_encoding(tokenizer)
            if tokenizer
            else tiktoken.get_encoding("cl100k_base")
        )

    def split_text(
        self,
        text: str,
    ) -> list[str]:
        """ """
        ...
