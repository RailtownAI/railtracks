from typing import List, Dict, Any, Optional, Callable
from .vector_store import VectorStore, SearchResponse, FetchResponse, Chunk


class MilvusVectorStore(VectorStore):
    """Milvus implementation of VectorStore. Currently only local Vector Stores"""

    @classmethod
    def class_init(cls, db_name: str):
        if not hasattr(cls, "_milvus"):
            # First object initialized so import pinecone and connect to server
            try:
                from pymilvus import MilvusClient

                cls._milvus = MilvusClient(db_name)
            except ImportError:
                raise ImportError(
                    "Milvus package is not installed. Please install railtracks[Milvus]."
                )

    def __init__(
        self,
        db_name: str,
        collection_name: str,
        dimension: Optional[int] = None,
        primary_field_name: str = "id",  # default is "id"
        id_type: str = "int",  # or "string",
        vector_field_name: str = "vector",  # default is  "vector"
        metric_type: str = "COSINE",
        auto_id: bool = False,
        timeout: Optional[float] = None,
        schema: Optional[CollectionSchema] = None,
        index_params: Optional[IndexParams] = None,
        **kwargs,
    ):
        self.class_init(db_name)
        self._collection_name = collection_name

        if not self._milvus.has_collection(collection_name):
            self._milvus.create_collection(
                collection_name=collection_name,
                dimension=dimension,
                primary_field_name=primary_field_name,
                id_type=id_type,
                vector_field_name=vector_field_name,
                metric_type=metric_type,
                auto_id=auto_id,
                timeout=timeout,
                schema=schema,
                index_params=index_params,
                **kwargs,
            )

    def upsert(
        self,
        collection_name: str,
        content: List[Chunk],
        timeout: Optional[float] = None,
        partition_name: Optional[str] = "",
        **kwargs,
    ):
        # Need to make content into a dict for usage
        self._milvus.upsert(
            collection_name=collection_name,
            data=content,
            timeout=timeout,
            partition_name=partition_name,
            **kwargs,
        )

    def fetch(self, ids: List[str]) -> List[FetchResponse]:
        results = self._milvus.query(self._collection_name, ids=ids)

        # Need to go through this and zip up results
        return results

    def search(
        self,
        query_embeddings: Optional[List[List[float]]] = None,
        query_texts: Optional[List[str]] = None,
        n_results: int = 10,
        where: Optional[Dict[str, Any]] = None,
        include: Optional[List[str]] = None,
    ) -> List[SearchResult]:
        pass

    def delete(
        self,
        collection_name: str,
        ids: Optional[Union[list, str, int]] = None,
        timeout: Optional[float] = None,
        filter: Optional[str] = None,
        partition_name: Optional[str] = None,
        **kwargs,
    ):
        self._milvus.delete(
            collection_name=collection_name,
            ids=ids,
            timeout=timeout,
            filter=filter,
            partition_name=partition_name,
            **kwargs,
        )

    # TODO verify this count is the way to go here
    def count(self) -> int:
        return self._milvus.get_collection_stats(self._collection_name)["count"]
