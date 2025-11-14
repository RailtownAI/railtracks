from typing import List, Dict, Any, Optional, Callable, Union
import os
from .vector_store import VectorStore, FetchResult, SearchResult, SearchResponse, FetchResponse, Metric, Chunk, Document
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
        pool_threads
        ):
        if not hasattr(cls, "_pc"):
            try:
                from pinecone import Pinecone
                from pinecone.inference.models.index_embed import IndexEmbed
                from pinecone import Vector
                # store imports on the class so other methods can reference them
                cls.Vector = Vector
                cls.IndexEmbed = IndexEmbed
                cls._pc = Pinecone(api_key=api_key,
                                host=host,
                                proxy_url=proxy_url,
                                proxy_headers=proxy_headers,
                                ssl_ca_certs=ssl_ca_certs,
                                ssl_verify=ssl_verify,
                                additional_headers=additional_headers,
                                pool_threads=pool_threads,
                                )
            except ImportError:
                    raise ImportError("Pinecone package is not installed. Please install railtracks[pinecone].")
    #TODO
    def __init__(
        self,
        index_name: str,
        collection_name: str,
        dimension: int,
        embedding_function: Callable[[List[str]], List[List[float]]], #TODO Fix this to have the right typing
        metric: Union[Metric, str] = Metric.l2,
        api_key: Optional[str] = os.getenv("PINECONE_API_KEY"),
        host: Optional[str] = None,
        proxy_url: Optional[str] = None,
        proxy_headers: Optional[Dict[str, str]] = None,
        ssl_ca_certs: Optional[str] = None,
        ssl_verify: Optional[bool] = None,
        additional_headers: Optional[Dict[str, str]] = {},
        pool_threads: Optional[int] = None,
        **kwargs: Any
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
            if embedding_function not in [x.model for x in self._pc.inference.list_models()]:
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
                    embed=IndexEmbed("embedding_function", {"text" : "chunk"}) #make sure we fix this to be proper embedding model
                    tags=tags,
                    deletion_protection=deletion_protection,
                    timeout=timeout,
                )

        self._collection_name = collection_name
        self._embedding_function = embedding_function
        self._collection = self._pc.Index(index_name)
        
    
    #Look into large file imports that pinecone supports and fix typing
    def upsert(
        self,
        content : List[Chunk] | List[Document] | List[str],
        batch_size : Optional[int] = None, 
    ):
            
        vectors = []
        if self.has_model:
            if isinstance(content, type(List[Chunk])):
                for chunk in content:
                    id = uuid4().int
                    values = self._embedding_function([chunk.content])[0]
                    metadata = chunk.metadata
                    metadata["content"] = chunk.content
                    if chunk.document:
                        metadata["document"] = chunk.document
                    vector = self.__class__.Vector(str(id),values, metadata=chunk.metadata)#TODO fix typing of values and possibly metadata
                    vectors.append(vector)
        
        self._collection.upsert(
            vectors,
            self._collection_name,
            batch_size=batch_size
            )

    #There is also documentation to fetch using query which is likely faster since it uses ANN but it won't guarantee you get the result back then so I'm using fetch
    def fetch(
            self,
            ids: List[str],
            ) -> FetchResponse:
        responses = FetchResponse()
        document = None
        results = self._collection.fetch(ids)
        for id in results.vectors:
            data = results.vectors[id]
            vec = data.values
            metadata = data.metadata
            if metadata and isinstance(metadata["content"], str):
                content = metadata["content"]
                if isinstance(metadata["document"], Document):
                    document = metadata["document"]
                    metadata.pop("document")
                metadata.pop("content")
                #TODO Check that this covers edge case if we empty the metadata?
                
            else:
                raise Exception #TODO Fix this control logic here
            responses.append(FetchResult(id, content, vec, document, metadata))
        
        return responses
    
    #Pinecone has support for embedding models actually. So we will need to check if the index has a model associated with it
    #Possibly add support for chunks being used as queries as well
    def search(
        self,
        queries : List[str],
        top_k: int = 10,
        where: Optional[Dict[str, Any]] = None,
        include_values: Optional[bool] = None,
        include_metadata : Optional[bool] = None,
    ) -> List[SearchResponse]:
        
        #search is what you would use to query with text
        if self.has_model:
            response = self._collection.search(
                namespace=self._collection_name,
                query=queries,
                rerank=rerank
            )
        else:
            #query is what you would use for vector

            vectors = self._embedding_function(queries)
            results = []
            for vec in vectors:
                results self._collection.query(
                    top_k=top_k,
                    vector=vec,
                    namespace=self._collection_name,
                    include_values=include_values,
                    include_metadata=include_metadata,
                )
    
    #This returns dict pinecone returns that other libs don't so inconsistency on return type but I think we let it be
    def delete(
        self,
        ids: Optional[List[str]] = None,
        delete_all: Optional[bool] = None,
        filter: Optional[Dict[str, Union[str, float, int, bool, List, dict]]] = None,
    ) -> Dict[str, Any]:
        
        deleted = self._collection.delete(
            ids,
            delete_all,
            self._collection_name,
            filter,
        )

        return deleted
    #TODO Test
    def count(self) -> int:
        return self._collection.describe_index_stats()["total_vector_count"]
