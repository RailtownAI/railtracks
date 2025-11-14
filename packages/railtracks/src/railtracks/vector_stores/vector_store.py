from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional, Callable, Mapping
from enum import Enum
from dataclasses import dataclass, field


class MetadataKeys(str, Enum):
    CONTENT = "__content__"
    DOCUMENT = "__document__"


class Metric(str, Enum):
    """
    Enumeration of supported distance/similarity metrics for vector comparisons.
    """

    cosine = "cosine"  # Cosine similarity
    l2 = "l2"  # Euclidean (L2) distance
    dot = "dot"  # Dot product similarity


class Document(str):
    content: str


@dataclass
class Chunk:
    """
    Chunk class to be used if you want to attach metadata and document data to chunks being upserted
    or if you want to use our chunker and immediately upsert the chunks
    """

    content: str
    document: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Ensure metadata is always a dict."""
        if self.metadata is None:
            self.metadata = {}


@dataclass
class SearchResult:
    """Container for a single search result from a vector store query."""

    id: str
    distance: float
    content: str
    vector: List[float]
    document: Optional[str] = None
    metadata: Dict[str, Any] | Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Ensure metadata is always a dict."""
        if self.metadata is None:
            self.metadata = {}


@dataclass
class FetchResult:
    """Container for a single fetch result from a vector store fetch."""

    id: str
    content: str
    vector: List[float]
    document: Optional[str] = None
    metadata: Dict[str, Any] | Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Ensure metadata is always a dict."""
        if self.metadata is None:
            self.metadata = {}


# For Readability
class SearchResponse(List[SearchResult]):
    """Containter for results of search"""


class FetchResponse(List[FetchResult]):
    """Container for results of a Fetch."""


class VectorStore(ABC):
    """Abstract base class for vector store implementations."""

    @abstractmethod
    def __init__(
        self,
        collection_name: str,
        embedding_function: Callable[[List[str]], List[List[float]]],
    ):
        """
        Initialize the vector store.

        Args:
            collection_name: Name of the collection/index
            embedding_function: Function to convert text to embeddings
        """
        pass

    @abstractmethod
    def upsert(
        self,
        content: List[Chunk] | List[str],
    ) -> List[str]:
        """
        Insert or update vectors in the store.

        Args:
            content: List of Chunk objects or raw text strings to be upserted

        Returns:
            List of IDs of the upserted vectors
        """
        pass

    @abstractmethod
    def fetch(self, ids: List[str]) -> FetchResponse:
        """
        Fetch vectors by their IDs.

        Args:
            ids: List of vector IDs to fetch

        Returns:
            FetchResponse containing the fetched vectors
        """
        pass

    @abstractmethod
    def search(
        self,
        query: List[Chunk] | List[str],
        n_results: int = 10,
        where: Optional[Dict[str, Any]] = None,
        include: Optional[List[str]] = None,
    ) -> List[SearchResponse]:
        """
        Query the vector store for similar vectors.

        Args:
            query: List of Chunk objects or raw text strings to query
            n_results: Number of results to return
            where: Filter conditions for metadata
            include: List of fields to include in results

        Returns:
            Dictionary containing query results with ids, distances, and metadata
        """
        pass

    @abstractmethod
    def delete(
        self, ids: Optional[List[str]] = None, where: Optional[Dict[str, Any]] = None
    ):
        """
        Delete vectors from the store.

        Args:
            ids: List of vector IDs to delete
            where: Filter conditions for deletion

        """
        pass

    @abstractmethod
    def count(self) -> int:
        """
        Get the total number of vectors in the collection.

        Returns:
            Total count of vectors
        """
        pass
