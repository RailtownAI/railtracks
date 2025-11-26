from abc import ABC, abstractmethod
from typing import Optional, Any, overload
import tiktoken

from .base_chunker import Chunk, BaseChunker

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
        self,
        chunk_size: int = 400,
        overlap: int = 200,
        tokenizer: Optional[str] = None
    ):
        super().__init__(chunk_size, overlap)
        self._tokenizer = (
            tiktoken.get_encoding(tokenizer)
            if tokenizer
            else tiktoken.get_encoding("cl100k_base")
        )

    @overload
    def chunk(
        self,
        *,
        text: str,
        document_name: Optional[str],
        metadata: dict[str, Any],
    ) -> list[Chunk]:
        """Chunk raw text into token-based segments."""
        ...

    @overload
    def chunk(
        self,
        *,
        document_path: str,
        document_name: Optional[str],
        metadata: dict[str, Any],
    ) -> list[Chunk]:
        """Chunk the contents of a document at the given path."""
        ...

    def chunk(
        self,
        *,
        text: Optional[str] = None,
        document_path: Optional[str] = None,
        document_name: Optional[str] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> list[Chunk]:
        """Split text or document content into token-based chunks.

        Exactly one of ``text`` or ``document_path`` must be provided.
        The produced chunks will be sized according to the configured
        token window and overlap.

        Args:
            text (Optional[str]): Raw text to chunk. Mutually exclusive with
                ``document_path``.
            document_path (Optional[str]): File whose contents should be chunked.
                Mutually exclusive with ``text``.
            document_name (Optional[str]): Name or identifier associated with
                the document. Applied to each generated chunk.
            metadata (Optional[dict[str, Any]]): Additional metadata to embed
                in each produced chunk.

        Returns:
            list[Chunk]: A list of generated chunk objects.

        Raises:
            ValueError: If both or neither of ``text`` and ``document_path`` are
                provided.
        """
        if text and not document_path:
            split_text = self._split_text(text)
            chunks = self._chunkify(
                split_text=split_text,
                document_name=document_name,
                metadata=metadata,
            )

        elif document_path and not text:
            try:
                with open(document_path, "r", encoding="utf-8") as f:
                    file_text = f.read()
            except FileNotFoundError:
                raise FileNotFoundError(f"Could not find document at path: {document_path}")
            except OSError as e:
                raise OSError(f"Error reading file '{document_path}': {e}")

            split_text = self._split_text(file_text)
            chunks = self._chunkify(
                split_text=split_text,
                document_name=document_name or document_path,
                metadata=metadata,
            )

        else:
            raise ValueError(
                "Must provide either text or document_path but not both."
            )
        
        return chunks

    def _split_text(self, text: str) -> list[str]:
        """Split raw text into token-based windows.

        The text is tokenized using the configured tokenizer, and then divided
        into windows of ``_chunk_size`` tokens with ``_overlap`` tokens of
        backward overlap.

        Args:
            text (str): The raw text to split.

        Returns:
            list[str]: A list of text segments decoded back from token windows.
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

    def _chunkify(
        self,
        split_text: list[str],
        document_name: Optional[str],
        metadata: Optional[dict[str, Any]] = None,
    ) -> list[Chunk]:
        """Convert split text segments into `Chunk` objects.

        Args:
            split_text (list[str]): Output from `_split_text`, containing
                sequential text segments.
            document_name (Optional[str]): Name of the source document.
            metadata (Optional[dict[str, Any]]): Metadata to store with each
                chunk.

        Returns:
            list[Chunk]: Chunk objects containing text content and metadata.
        """
        chunks = []
        for segment in split_text:
            chunks.append(
                Chunk(
                    content=segment,
                    document=document_name,
                    metadata=metadata,
                )
            )
        return chunks