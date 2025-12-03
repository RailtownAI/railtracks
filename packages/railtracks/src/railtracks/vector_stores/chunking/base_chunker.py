from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Optional
from uuid import uuid4

from .media_parser import MediaParser


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
    metadata: Optional[dict[str, Any]] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Normalize metadata and ensure identifier is populated."""
        if self.metadata is None:
            self.metadata = {}
        if self.id is None:
            self.id = str(uuid4())


class BaseChunker(ABC):
    """Abstract base class for chunking strategies.

    A chunker splits input text ``Chunk`` objects. Specific chunking
    strategies should subclass this class and implement the abstract
    ``chunk`` method.

    Args:
        chunk_size (int): Specifies number of tokens per chunk to
            varying degree depending on implementation.
            Defaults to 400
        overlap (int): Specifies number of tokens to overlap
            between adjacent chunks to varying degree depending
            on implementation. Defaults to 200.

    Attributes:
        _chunk_size (int): Internal storage for chunk size.
        _overlap (int): Internal storage for overlap size.
    """

    def __init__(
        self,
        chunk_size: int = 400,
        overlap: int = 200,
    ):
        if not overlap < chunk_size:
            raise ValueError("'overlap' must be smaller than 'chunk_size'.")
        if not chunk_size > 0 or not overlap >= 0:
            raise ValueError(
                "'chunk_size' must be greater than 0 and 'overlap' must be at least 0 "
            )

        self._chunk_size = chunk_size
        self._overlap = overlap

    @property
    def chunk_size(self) -> int:
        return self._chunk_size

    @chunk_size.setter
    def chunk_size(self, value: int):
        if not self.overlap < value:
            raise ValueError("'overlap' must be smaller than 'chunk_size'.")
        if not value > 0:
            raise ValueError("'chunk_size' must be greater than 0")
        self._chunk_size = value

    @property
    def overlap(self) -> int:
        return self._overlap

    @overlap.setter
    def overlap(self, value: int):
        if not value < self._chunk_size:
            raise ValueError("'overlap' must be smaller than 'chunk_size'.")
        if not value >= 0:
            raise ValueError("'overlap' must be at least 0")
        self._overlap = value

    def chunk(
        self,
        text: str,
        document: Optional[str] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> list[Chunk]:
        """Split text into list of chunks.


        Args:
            text (str): Raw text to chunk.
            document (Optional[str]): Identifier associated with the
                document or text source. Applied to each output chunk.
            metadata (dict[str, Any]): Additional metadata stored in each
                created chunk.

        Returns:
            list[Chunk]: A list of chunk objects produced by the chunking
            strategy.
        """
        text_chunk_list = self.split_text(text)
        chunks = self.make_into_chunks(text_chunk_list, document, metadata)

        return chunks

    def chunk_from_file(
        self,
        path: str,
        encoding: Optional[str] = None,
        document: Optional[str] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> list[Chunk]:
        """Split text into list of chunks from a specified file.

        Args:
            path (str): File path to the input text source. Currently only `.pdf`
                and `.txt` files are supported.
            document (Optional[str]): Identifier associated with the
                document or text source. Applied to each created chunk.
            metadata (dict[str, Any]): Additional metadata stored in each
                created chunk.

        Returns:
            list[Chunk]: A list of chunk objects produced by the chunking
                strategy.

        """

        text = MediaParser.get_text(path, encoding=encoding)

        return self.chunk(text, document, metadata)

    @abstractmethod
    def split_text(
        self,
        text: str,
    ) -> list[str]:
        """Split text into text chunks.


        Args:
            text (str): Raw text to chunk.

        Returns:
            list[str]: A list of strings produced by the chunking strategy.
        """
        pass

    @classmethod
    def make_into_chunks(
        cls,
        text_chunks: list[str],
        document: Optional[str] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> list[Chunk]:
        """Make list of text chunks into chunk type with associated attributes.


        Args:
            text_chunks (list[str]): Raw text to chunk.
            document (Optional[str]): Identifier associated with the
                document or text source. Applied to each output chunk.
            metadata (dict[str, Any]): Additional metadata stored in each
                created chunk.

        Returns:
            list[Chunk]: A list of chunk objects produced by the chunking
            strategy.

        """

        chunks = []
        for text_chunk in text_chunks:
            chunks.append(
                Chunk(
                    content=text_chunk,
                    document=document,
                    metadata=dict(metadata) if metadata is not None else None,
                )
            )
        return chunks
