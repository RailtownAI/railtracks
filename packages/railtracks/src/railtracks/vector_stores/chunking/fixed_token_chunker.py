from typing import Optional

import tiktoken

from .base_chunker import BaseChunker


class FixedTokenChunker(BaseChunker):
    """A chunker that splits text strictly by token count.

    This implementation divides text using a fixed token window, optionally
    with overlap between chunks. Tokenization is performed using `tiktoken`
    and defaults to the `cl100k_base` tokenizer unless otherwise specified.

    Args:
        chunk_size (int): Maximum number of tokens allowed in a produced chunk.
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
        """Split raw text into token-based windows.

        The text is tokenized using the configured tokenizer, and then divided
        into windows of ``_chunk_size`` tokens with ``_overlap`` tokens of
        backward overlap.

        Args:
            text (str): Raw text to split.

        Returns:
            list[str]: A list of text segments decoded back from token windows.
                Note : returns an empty list if passed an empty string
        """

        text_chunks = []
        tokens = self._tokenizer.encode(text)
        start = 0

        while start < len(tokens):
            end = min(start + self._chunk_size, len(tokens))
            token_window = tokens[start:end]
            text_chunks.append(self._tokenizer.decode(token_window))
            start += self._chunk_size - self._overlap

        return text_chunks
