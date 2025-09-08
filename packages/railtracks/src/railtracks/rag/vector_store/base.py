from __future__ import annotations

import abc
import enum
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Union

Vector = List[float]  # Alias for readability


class Metric(str, enum.Enum):
    """
    Enumeration of supported distance/similarity metrics for vector comparisons.
    """

    cosine = "cosine"  # Cosine similarity
    l2 = "l2"  # Euclidean (L2) distance
    dot = "dot"  # Dot product similarity


@dataclass
class VectorRecord:
    """
    Represents a single item in the vector store.

    Attributes:
        id: Unique identifier for the record.
        vector: Numeric feature vector.
        text: Optional original text that produced the vector.
        metadata: Optional dictionary with any custom metadata (e.g. category, timestamp).
    """

    id: str
    vector: Vector
    text: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = field(default_factory=dict)

    def json(self):
        """
        Convert the VectorRecord to a JSON-serializable dictionary.

        Returns:
            A dictionary representation of the VectorRecord.
        """
        return {
            "id": self.id,
            "vector": self.vector,
            "text": self.text,
            "metadata": self.metadata,
        }


@dataclass
class SearchEntry:
    """
    Represents a result from a similarity search in the vector store.

    Attributes:
        score: Similarity or distance score as determined by the `Metric`.
        record: The VectorRecord that matched the query.
        metadata: Optional metadata for display or further processing.
    """

    score: float
    record: VectorRecord
    metadata: Optional[Dict[str, Any]] = None

    def json(self):
        """
        Convert the SearchEntry to a JSON-serializable dictionary.

        Returns:
            A dictionary representation of the SearchEntry.
        """
        return {
            "score": self.score,
            "record": self.record.json(),
            "metadata": self.metadata,
        }


class SearchResult(list[SearchEntry]):
    """
    A list of SearchEntry with convenience methods.
    Behaves like a normal list (append, extend, iterate, index, etc.).
    """

    def __init__(self, entries: Optional[Iterable[SearchEntry]] = None):
        super().__init__(entries or [])

    def json(self) -> Dict[str, Any]:
        """Convert to a JSON-serializable dictionary."""
        return {"results": [entry.json() for entry in self]}

    def to_list_of_texts(self) -> List[str]:
        """Extract non-empty record.text values."""
        return [entry.record.text for entry in self if entry.record.text is not None]


class AbstractVectorStore(abc.ABC):
    """
    Abstract base class for a vector store interface.
    Concrete implementations must provide persistent storage and similarity search.
    """

    metric: Metric  # Defines how vector similarity is computed (must be set in implementation)

    # ---------- CRUD ----------

    @abc.abstractmethod
    def add(
        self,
        texts_or_records: Sequence[Union[str, VectorRecord]],
        *,
        embed: bool = True,
        metadata: Optional[Sequence[Dict[str, Any]]] = None,
    ) -> List[str]:
        """
        Add new vectors (or texts to be embedded) to the store.

        Args:
            texts_or_records: A sequence of texts (if embed=True) or full VectorRecord objects.
            embed: If True, input texts will be encoded to vectors first. If False, they are expected to be VectorRecords.
            metadata: Optional sequence of metadata dicts, aligned with input texts/records (ignored if records already have metadata).

        Returns:
            List of ids for the added records.
        """
        ...

    @abc.abstractmethod
    def search(
        self,
        query: Union[str, Vector],
        top_k: int = 5,
        *,
        embed: bool = True,
    ) -> List[SearchEntry]:
        """
        Search for the top-k most similar vectors in the store to a query string or vector.

        Args:
            query: Input text (if embed=True) or vector to search against the collection.
            k: Number of top results to return.
            embed: If True, the query is assumed to be a string to embed.

        Returns:
            List of search results ordered by decreasing similarity (or increasing distance).
        """
        ...

    @abc.abstractmethod
    def delete(self, ids: Sequence[str]) -> int:
        """
        Remove records from the vector store by their ID.

        Args:
            ids: Sequence of ids to remove.

        Returns:
            Number of records deleted.
        """
        ...

    @abc.abstractmethod
    def update(
        self,
        id: str,
        new_text_or_vector: Union[str, Vector],
        *,
        embed: bool = True,
        **metadata,
    ) -> None:
        """
        Update a record, replacing its vector (or text) and/or metadata.

        Args:
            id: ID of the record to update.
            new_text_or_vector: New text (if embed=True) or vector.
            embed: Whether to embed the new text input. Ignored if passing a vector.
            **metadata: Key-value pairs to update in the record's metadata.

        Returns:
            None
        """
        ...

    # ---------- Misc utility methods ----------

    @abc.abstractmethod
    def count(self) -> int:
        """
        Return the number of records currently stored.
        """
        ...

    @abc.abstractmethod
    def persist(self, path: Optional[Union[str, Path]] = None) -> None:
        """
        Save the store's contents to disk for later reloading.

        Args:
            path: Optional filesystem path to save to. If not provided, use the store's default path.

        Returns:
            None
        """
        ...

    @classmethod
    @abc.abstractmethod
    def load(cls, path: Union[str, Path]) -> AbstractVectorStore:
        """
        Rehydrate a vector store previously saved to disk.

        Args:
            path: The filesystem path to load from.

        Returns:
            An instance of the concrete VectorStore subclass.
        """
        ...
