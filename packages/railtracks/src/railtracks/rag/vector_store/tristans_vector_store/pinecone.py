from typing import List, Dict, Any, Optional, Callable
from .vector_store import VectorStore

class PineconeVectorStore(VectorStore):
    """Pinecone implementation of VectorStore."""

    def __init__(
        self,
        collection_name: str,
        embedding_function: Callable[[List[str]], List[List[float]]],
        client_object : Any,
        dimension: int,
    ):
        self.collection_name = collection_name
        self.embedding_function = embedding_function
        self.client_object = client_object
        self.dimension = dimension
    
    def upsert(
        self,
        ids: List[str],
        embeddings: Optional[List[List[float]]] = None,
        documents: Optional[List[str]] = None,
        metadatas: Optional[List[Dict[str, Any]]] = None
    ):
        pass
    
    def fetch(self, ids: List[str]) -> List[SearchResult]:
        pass
    
    def query(
        self,
        query_embeddings: Optional[List[List[float]]] = None,
        query_texts: Optional[List[str]] = None,
        n_results: int = 10,
        where: Optional[Dict[str, Any]] = None,
        include: Optional[List[str]] = None
    ) -> List[SearchResult]:
        pass
    
    def delete(
        self,
        ids: Optional[List[str]] = None,
        where: Optional[Dict[str, Any]] = None
    ):
        pass
    
    def count(self) -> int:
        return self._count