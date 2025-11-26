from abc import ABC, abstractmethod
from typing import Optional, Any, overload
from dataclasses import dataclass, field
from uuid import uuid4


@dataclass
class Chunk:
    """Structured chunk that can be upserted to a vector store.

    Attributes:
        content (str): The raw chunk text.
        id (Optional[str]): Identifier for the chunk. If not provided, a UUID
            is automatically generated in ``__post_init__``.
        document (Optional[str]): Optional document identifier or content
            associated with the chunk.
        metadata (dict[str, Any]): Arbitrary key-value metadata associated
            with this chunk. Defaults to an empty dictionary.

    """

    content: str
    id: Optional[str] = None
    document: Optional[str] = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Normalize metadata and ensure identifier is populated."""
        if self.metadata is None:
            self.metadata = {}
        if self.id is None:
            self.id = str(uuid4())


class BaseChunker(ABC):
    """Abstract base class for chunking strategies.

    A chunker splits input text or documents into ``Chunk`` objects and can
    optionally embed them using an embedding model. Specific chunking
    strategies should subclass this class and implement the abstract
    ``chunk`` method.

    Args:
        chunk_size (int): Maximum number of characters allowed in a produced
            chunk. Defaults to 400.
        overlap (int): Number of characters of overlap to retain between
            adjacent chunks. Defaults to 200.

    Attributes:
        _chunk_size (int): Internal storage for chunk size.
        _overlap (int): Internal storage for overlap size.
    """

    def __init__(
        self,
        chunk_size: int = 400,
        overlap: int = 200,
    ):
        assert overlap < chunk_size, "'overlap' must be smaller than 'chunk_size'."
        assert chunk_size > 0 and overlap >= 0, "'chunk_size' must be greater than 0 and 'overlap' must be at least 0 "
        self._chunk_size = chunk_size
        self._overlap = overlap

    @property
    def chunk_size(self) -> int:
        return self._chunk_size

    @chunk_size.setter
    def chunk_size(self, value: int):
        assert self.overlap < value, "'overlap' must be smaller than 'chunk_size'."
        assert value > 0, "'chunk_size' must be greater than 0 and "
        self._chunk_size = value

    @property
    def overlap(self) -> int:
        return self._overlap

    @overlap.setter
    def overlap(self, value: int):
        assert value < self._chunk_size, "'overlap' must be smaller than 'chunk_size'."
        assert value >= 0, "'overlap' must be at least 0 "
        self._overlap = value

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
        """Split text or document content into chunks.

        Subclasses must implement the logic for how text is segmented into
        ``Chunk`` objects. Either ``text`` or ``document_path`` must be
        supplied, but not both.

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
