from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Optional, TypeVar, Union, overload, Literal

from .chunking.base_chunker import Chunk

T = TypeVar("T")

class MetadataKeys(str, Enum):
    """Well-known metadata keys used by vector store wrappers.

    These keys are used internally to store the original content/document
    alongside the vector so callers do not need to rely on provider-specific
    metadata keys.
    """

    CONTENT = "__content__"
    DOCUMENT = "__document__"

class Fields(str, Enum):
    """Enum to use when specifying which fields should be returned.

    These keys are used internally to store the original content/document
    alongside the vector so callers do not need to rely on provider-specific
    metadata keys. It is also used to specify which fields to include in search
    results.
    """
    DOCUMENT = "document"
    DISTANCE = "distance"
    VECTOR = "vector"
    METADATA = "metadata"
    NOTHING = "nothing"


class Metric(str, Enum):
    """Enumeration of supported distance/similarity metrics.

    Values of this enum are passed to underlying vector stores where supported.
    """

    cosine = "cosine"
    """Cosine similarity."""

    l2 = "l2"
    """Euclidean (L2) distance."""

    dot = "dot"
    """Dot-product similarity."""


@dataclass
class SearchResult:
    """Container that represents a single search result given a query.

    Attributes:
        id: Identifier for the matched vector.
        distance: Distance or similarity score (interpretation depends on `Metric`).
        content: The stored content associated with the vector.
        vector: The embedding vector as a list of floats if dense or dict with indices and values if sparse.
        document: Optional document content or id associated with the vector.
        metadata: Arbitrary metadata dictionary attached to the vector.
    """

    id: str
    content: str
    distance: Optional[float] = None
    vector: Optional[list[float] | dict[str, list[int | float]]] = None
    document: Optional[str] = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Ensure metadata is always a dict."""
        if self.metadata is None:
            self.metadata = {}


@dataclass
class FetchResult:
    """Container that represents a single fetch result returned when requesting specific ids.

    Attributes:
        id: Identifier for the matched vector.
        content: The stored content associated with the vector.
        vector: The embedding vector as a list of floats if dense or dict with indices and values if sparse.
        document: Optional document content or id associated with the vector.
        metadata: Arbitrary metadata dictionary attached to the vector.
    """

    id: str
    content: str
    vector: Optional[list[float] | dict[str, list[int | float]]] = None
    document: Optional[str] = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Ensure metadata is always a dict."""
        if self.metadata is None:
            self.metadata = {}


# For Readability make type aliases
SearchResponse = list[SearchResult]
FetchResponse = list[FetchResult]
OneOrMany = Union[T, list[T]]


class VectorStore(ABC):
    """Abstract base class for all vector-store implementations.

    Implementations should provide consistent semantics for the methods below
    so higher-level code can switch stores without changing business logic.
    """

    def __init__(
        self,
        collection_name: str,
        embedding_model: Callable[[list[str]], list[list[float]]],
    ):
        """Initialize the vector store instance.

        Args:
            collection_name: Name of the collection to use or create.
            embedding_model: Callable that converts a list of strings into a
                list of embeddings(a list of floats).
        """
        self._collection_name = collection_name
        self._embedding_model = embedding_model

    @overload
    def upsert(
        self,
        content: Chunk | str,
    ) -> str: ...

    @overload
    def upsert(
        self,
        content: list[Chunk | str],
    ) -> list[str]: ...

    @abstractmethod
    def upsert(
        self,
        content: OneOrMany[Chunk | str],
    ) -> OneOrMany[str]:
        """Insert or update a batch of vectors into the store.

        The implementation may accept either a list of :class:`Chunk` instances
        (which include metadata and optional document ids) or a list of raw
        strings. Implementations should generate and return stable identifiers
        for the inserted vectors.

        Args:
            content: A singular or list of chunks or strings to add to vector store.

        Returns:
            A singular or list of string ids for the upserted vectors.
        """
        pass

    @abstractmethod
    def fetch(self, ids: OneOrMany[str]) -> FetchResponse:
        """Fetch vectors for the given identifiers.

        Args:
            ids: A singular or list of vector ids to retrieve.

        Returns:
            A :class:`FetchResponse` containing the results in the same order
            as the requested ids.
        """
        pass

    @overload
    def search(
        self,
        query: Chunk | str,
        top_k: int = 10,
        where: Optional[dict[str, Any]] = None,
        include: Optional[list[str]] = None,
    ) -> SearchResponse: ...

    @overload
    def search(
        self,
        query: list[Chunk] | list[str],
        top_k: int = 10,
        where: Optional[dict[str, Any]] = None,
        include: Optional[list[str]] = None,
    ) -> list[SearchResponse]: ...

    @abstractmethod
    def search(
        self,
        query: OneOrMany[Chunk] | OneOrMany[str],
        top_k: int = 10,
        where: Optional[dict[str, Any]] = None,
        include: Optional[list[str]] = None,
    ) -> OneOrMany[SearchResponse]:
        """Perform a similarity search for the provided queries.

        Args:
            query: A list of query chunks or raw strings.
            top_k: Number of nearest neighbours to return per query.
            where: Optional filter to apply on metadata.
            include: Optional list of result fields to include.

        Returns:
            A list of or singular :class:`SearchResponse` objects, one per query.
        """
        pass

    @abstractmethod
    def delete(self, ids: OneOrMany[str], where: Optional[dict[str, Any]] = None):
        """Remove vectors from the store by id or metadata filter.

        Args:
            ids: Optional list of ids to remove.
            where: Optional metadata filter to delete matching vectors.
        """
        pass

    @abstractmethod
    def count(self) -> int:
        """Return the total number of vectors stored in the collection.

        Returns:
            The total count of indexed vectors.
        """
        pass

    def _one_or_many(self, item: OneOrMany[T]) -> tuple[bool, list[T]]:
        """make an item a list if not already one and return whether it was originally a list.

        Args:
            item: The thing to check for whether it's a list or not.

        Returns:
            A tuple where the first element is a boolean indicating whether the
            input was originally a list, and the second element is the item
            itself as a list.
        """

        if isinstance(item, list):
            return True, item
        
        else:
            return False, [item]
