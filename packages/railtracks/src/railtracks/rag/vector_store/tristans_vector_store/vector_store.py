from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional, Callable, Mapping
from enum import Enum
from dataclasses import dataclass, field
from pinecone import Vector



class Metric(str, Enum):
    """
    Enumeration of supported distance/similarity metrics for vector comparisons.
    """

    cosine = "cosine"  # Cosine similarity
    l2 = "l2"  # Euclidean (L2) distance
    dot = "dot"  # Dot product similarity

class Document(str):
    content :str

@dataclass
class Chunk:
    """Chunk class to be used when upserting to collections"""
    
    content :str
    document: Optional[Document] = None
    metadata: Dict[str, Any]= field(default_factory=dict)

    def __post_init__(self) -> None:
        """Ensure metadata is always a dict."""
        if self.metadata is None:
            self.metadata = {}

@dataclass
class SearchResult:
    """Container for a single search result from a vector store query."""

    id: str
    distance : float
    content :str
    vector : List[float]
    document: Optional[Document] = None
    metadata: Dict[str, Any] | Mapping[str, Any] = field(default_factory=dict)
    
    def __post_init__(self) -> None:
        """Ensure metadata is always a dict."""
        if self.metadata is None:
            self.metadata = {}
@dataclass
class FetchResult:
    """Container for a single fetch result from a vector store fetch."""
    
    id: str
    content :str
    vector : List[float]
    document: Optional[Document] = None
    metadata: Dict[str, Any] | Mapping[str, Any] = field(default_factory=dict)
    
    def __post_init__(self) -> None:
        """Ensure metadata is always a dict."""
        if self.metadata is None:
            self.metadata = {}
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
        client_object : Any, #Here once we implement will be the api object we interact with for user
        dimension: int,
    ):
        """
        Initialize the vector store.
        
        Args:
            collection_name: Name of the collection/index
            embedding_function: Function to convert text to embeddings
            dimension: Dimension of the embedding vectors
            **kwargs: Additional store-specific parameters
        """
        pass

    #Idea is to accept Chunks, Documents, or strs
    @abstractmethod
    def upsert(
        self,
        ids: List[str],
        embeddings: Optional[List[List[float]]] = None,
        documents: Optional[List[str]] = None,
        metadatas: Optional[List[Dict[str, Any]]] = None
    ):
        """
        Insert or update vectors in the store.
        
        Args:
            ids: List of unique identifiers
            embeddings: List of embedding vectors (optional if documents provided)
            documents: List of text documents to embed (optional if embeddings provided)
            metadatas: List of metadata dictionaries
            
        Returns:
            Dictionary containing operation results
        """
        pass
    
    @abstractmethod
    def fetch(
        self,
        ids: List[str]
    ) -> List[FetchResponse]:
        """
        Fetch vectors by their IDs.
        
        Args:
            ids: List of vector IDs to fetch
            
        Returns:
            Dictionary containing fetched vectors and metadata
        """
        pass
    
    @abstractmethod
    def search(
        self,
        query_embeddings: Optional[List[List[float]]] = None,
        query_texts: Optional[List[str]] = None,
        n_results: int = 10,
        where: Optional[Dict[str, Any]] = None,
        include: Optional[List[str]] = None
    ) -> List[SearchResponse]:
        """
        Query the vector store for similar vectors.
        
        Args:
            query_embeddings: List of query embedding vectors
            query_texts: List of query texts to embed
            n_results: Number of results to return
            where: Filter conditions for metadata
            include: List of fields to include in results
            
        Returns:
            Dictionary containing query results with ids, distances, and metadata
        """
        pass
    
    @abstractmethod
    def delete(
        self,
        ids: Optional[List[str]] = None,
        where: Optional[Dict[str, Any]] = None
    ):
        """
        Delete vectors from the store.
        
        Args:
            ids: List of vector IDs to delete
            where: Filter conditions for deletion
            
        Returns:
            Dictionary containing deletion results
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
