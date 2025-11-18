from typing import Any, Callable, Dict, Optional, Union
import os
from .vector_store_base import (
    Chunk,
    FetchResponse,
    FetchResult,
    MetadataKeys,
    Metric,
    OneOrMany,
    SearchResponse,
    SearchResult,
    VectorStore,
)
from uuid import uuid4


class PineconeVectorStore(VectorStore):
    """Pinecone implementation of VectorStore."""

    @classmethod
    def class_init(
        cls,
        api_key,
        host,
        proxy_url,
        proxy_headers,
        ssl_ca_certs,
        ssl_verify,
        additional_headers,
        pool_threads,
    ):
        if not hasattr(cls, "_pc"):
            try:
                from pinecone import Pinecone
                from pinecone.inference.models.index_embed import IndexEmbed
                from pinecone import Vector

                # store imports on the class so other methods can reference them
                cls.Vector = Vector
                cls.IndexEmbed = IndexEmbed
                cls._pc = Pinecone(
                    api_key=api_key,
                    host=host,
                    proxy_url=proxy_url,
                    proxy_headers=proxy_headers,
                    ssl_ca_certs=ssl_ca_certs,
                    ssl_verify=ssl_verify,
                    additional_headers=additional_headers,
                    pool_threads=pool_threads,
                )
            except ImportError:
                raise ImportError(
                    "Pinecone package is not installed. Please install railtracks[pinecone]."
                )

    def __init__(
        self,
        index_name: str,
        collection_name: str,
        dimension: int,
        embedding_function: Callable[[list[str]], list[list[float]]],
        metric: Union[Metric, str] = Metric.dot,
        api_key: Optional[str] = os.getenv("PINECONE_API_KEY"),
        host: Optional[str] = None,
        proxy_url: Optional[str] = None,
        proxy_headers: Optional[Dict[str, str]] = None,
        ssl_ca_certs: Optional[str] = None,
        ssl_verify: Optional[bool] = None,
        additional_headers: Optional[Dict[str, str]] = None,
        pool_threads: Optional[int] = None,
        **kwargs: Any,
    ):
        PineconeVectorStore.class_init(
            api_key,
            host,
            proxy_url,
            proxy_headers,
            ssl_ca_certs,
            ssl_verify,
            additional_headers,
            pool_threads,
        )

        self.has_model = True

        if not self._pc.has_index(index_name):
            """
            This is to create an index in pinecone if it doesn't exist yet.
            We call an index a collection in our framework as is common in other vector stores.
            Pinecone is annoying and has collections as well but they are a different concept.
            We should look into supporting those later because they are relevent.
            """
            if embedding_function not in [
                x.model for x in self._pc.inference.list_models()
            ]:
                self._pc.create_index(
                    name=index_name,
                    spec=spec,
                    dimension=dimension,
                    metric=metric,
                    timeout=timeout,
                    deletion_protection=deletion_protection,
                    vector_type=vector_type,
                )
                self.has_model = False
            else:
                self._pc.create_index_for_model(
                    name=index_name,
                    cloud="aws",
                    region="us-west-2",
                    embed=IndexEmbed(
                        "embedding_function", {"text": "chunk"}
                    ),  # make sure we fix this to be proper embedding model
                    tags=tags,
                    deletion_protection=deletion_protection,
                    timeout=timeout,
                )

        self._collection_name = collection_name
        self._embedding_function = embedding_function
        self._collection = self._pc.Index(index_name)

    # Look into large file imports that pinecone supports and fix typing
    def upsert(
        self,
        content: OneOrMany[Chunk] | OneOrMany[str],
        batch_size: Optional[int] = None,
    ) -> OneOrMany[str]:
        # Normalize input to list
        if isinstance(content, (str, Chunk)):
            content_list = [content]
        else:
            content_list = list(content)
        
        vectors = []
        ids = []
        
        if self.has_model:
            for item in content_list:
                id = str(uuid4().int)
                ids.append(id)
                
                if isinstance(item, Chunk):
                    values = self._embedding_function([item.content])[0]
                    metadata = dict(item.metadata)
                    metadata[MetadataKeys.CONTENT.value] = item.content
                    if item.document:
                        metadata[MetadataKeys.DOCUMENT.value] = item.document
                else:
                    values = self._embedding_function([item])[0]
                    metadata = {MetadataKeys.CONTENT.value: item}
                
                vector = self.__class__.Vector(
                    id, values, metadata=metadata
                )
                vectors.append(vector)
        
        self._collection.upsert(vectors, self._collection_name, batch_size=batch_size)
        
        # Return in same shape as input (OneOrMany)
        return ids if len(ids) > 1 else ids[0] if ids else []

    # There is also documentation to fetch using query which is likely faster since it uses ANN but it won't guarantee you get the result back then so I'm using fetch
    def fetch(
        self,
        ids: OneOrMany[str],
    ) -> FetchResponse:
        # Normalize ids to list
        if isinstance(ids, str):
            ids_list = [ids]
        else:
            ids_list = list(ids)
        
        responses = FetchResponse()
        results = self._collection.fetch(ids_list)
        
        for id in results.vectors:
            data = results.vectors[id]
            vec = data.values
            metadata = dict(data.metadata) if data.metadata else {}
            
            # Extract content from metadata
            content_value = metadata.get(MetadataKeys.CONTENT.value)
            if not isinstance(content_value, str):
                raise ValueError(f"Content not found or invalid for id {id}")
            
            # Extract document from metadata
            document_value = metadata.get(MetadataKeys.DOCUMENT.value)
            if document_value:
                document = str(document_value) if isinstance(document_value, str) else None
            else:
                document = None
            
            # Remove internal keys from metadata
            metadata.pop(MetadataKeys.CONTENT.value, None)
            metadata.pop(MetadataKeys.DOCUMENT.value, None)
            
            responses.append(FetchResult(
                id=id,
                content=content_value,
                vector=list(vec),
                document=document,
                metadata=metadata,
            ))
        
        return responses

    # Pinecone has support for embedding models actually. So we will need to check if the index has a model associated with it
    # Possibly add support for chunks being used as queries as well
    def search(
        self,
        query: OneOrMany[Chunk] | OneOrMany[str],
        top_k: int = 10,
        where: Optional[dict[str, Any]] = None,
        include: Optional[list[str]] = None,
    ) -> OneOrMany[SearchResponse]:
        # Normalize query to list of strings
        if isinstance(query, (str, Chunk)):
            query_list = [query]
        else:
            query_list = list(query)
        
        query_texts: list[str] = []
        for q in query_list:
            if isinstance(q, Chunk):
                query_texts.append(q.content)
            else:
                query_texts.append(q)
        
        # TODO: Implement search/query logic for Pinecone
        # search is what you would use to query with text (requires model)
        # query is what you would use for vector queries
        
        if self.has_model:
            # Use Pinecone's text search if a model is available
            response = self._collection.search(
                namespace=self._collection_name,
                query=query_texts,
            )
        else:
            # Fall back to vector search by embedding the query texts
            vectors = self._embedding_function(query_texts)
            results = []
            for vec in vectors:
                result = self._collection.query(
                    top_k=top_k,
                    vector=vec,
                    namespace=self._collection_name,
                    filter=where,
                )
                results.append(result)
            response = results
        
        # TODO: Parse Pinecone response and convert to SearchResponse objects
        # Return empty list for now as placeholder
        return []

    # This returns dict pinecone returns that other libs don't so inconsistency on return type but I think we let it be
    def delete(
        self,
        ids: OneOrMany[str],
        where: Optional[dict[str, Any]] = None,
    ) -> None:
        # Normalize ids to list for Pinecone client
        if isinstance(ids, str):
            ids_list = [ids]
        else:
            ids_list = list(ids)
        
        # Pinecone delete signature: delete(ids=None, delete_all=None, namespace=None, filter=None)
        self._collection.delete(
            ids=ids_list,
            namespace=self._collection_name,
            filter=where,
        )

    # TODO Test
    def count(self) -> int:
        return self._collection.describe_index_stats()["total_vector_count"]
