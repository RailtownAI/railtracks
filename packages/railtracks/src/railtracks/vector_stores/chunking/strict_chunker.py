from abc import ABC, abstractmethod
from typing import Optional, Any, Callable, overload

from railtracks.rag.embedding_service import EmbeddingService
from .base_chunker import Chunk, BaseChunker

class StrictChunker(BaseChunker):
    """A naive chunker that splits text strictly by token size.

    Args:
        chunk_size (int): Maximum number of characters allowed in a produced
            chunk. Defaults to 400.
        overlap (int): Number of characters of overlap to retain between
            adjacent chunks. Defaults to 200.
        embedding_model (Callable[[list[str]], list[list[float]]]): A callable
            that accepts a list of strings and returns embedding vectors.
            Defaults to ``EmbeddingService().embed``.

    Attributes:
        _chunk_size (int): Internal storage for chunk size.
        _overlap (int): Internal storage for overlap size.
        _embedding_model (Callable): The embedding model used for converting
            text into embedding vectors.
    """

    # TODO: Default a lightweight embedding model
    def __init__(
        self,
        chunk_size: int = 400,
        overlap: int = 200,
        tokenizer: Callable[[list[str]], list[list[float]]] = EmbeddingService().embed,
    ):
        self._chunk_size = chunk_size
        self._overlap = overlap
        self._tokenizer = tokenizer

    @overload
    def chunk(
        self,
        *,
        text: str,
        document_name: Optional[str],
        metadata: dict[str, Any],
    ) -> list[Chunk]:
        ...

    @overload
    def chunk(
        self,
        *,
        document_path: str,
        document_name: Optional[str],
        metadata: dict[str, Any],
    ) -> list[Chunk]:
        ...

    @abstractmethod
    def chunk(
        self,
        *,
        text: Optional[str] = None,
        document_path: Optional[str] = None,
        document_name: Optional[str] = None,
        metadata: dict[str, Any] = {},
    ) -> list[Chunk]:
        """Split text or document content into chunks of specified size.

        Args:
            text (Optional[str]): Raw text to chunk. Mutually exclusive with
                ``document_path``.
            document_path (Optional[str]): Path to a file whose contents should
                be chunked. Mutually exclusive with ``text``.
            document_name (Optional[str]): Identifier associated with the
                document or text source. Applied to each output chunk.
            metadata (dict[str, Any]): Additional metadata stored in each
                created chunk.

        Returns:
            list[Chunk]: A list of chunk objects produced by the chunking
            strategy.

        Raises:
            ValueError: If neither ``text`` nor ``document_path`` is provided.
        """
        pass
