import os
from typing import Any, Callable, Dict, Optional, Union, overload
from uuid import uuid4

from .vector_store_base import (
    Chunk,
    FetchResponse,
    FetchResult,
    Metric,
    OneOrMany,
    SearchResponse,
    VectorStore,
)


class PineconeVectorStore(VectorStore):
    """Pinecone implementation of VectorStore."""

    @classmethod
    def class_init(
        cls,
        api_key : str,
        index_name : str,
    ) -> str:
        if not hasattr(cls, "_pc"):
            try:
                from pinecone import Pinecone, Vector
                from pinecone.inference.models.index_embed import IndexEmbed

                # store imports on the class so other methods can reference them
                cls.Vector = Vector
                cls.IndexEmbed = IndexEmbed
                cls._pc = Pinecone(api_key=api_key)
                if cls._pc.has_index(index_name):
                    index_details = cls._pc.describe_index(index_name)
                    host = index_details["host"]
                    return host
                    
                cls._index = 
            except ImportError:
                raise ImportError(
                    "Pinecone package is not installed. Please install railtracks[pinecone]."
                )
            
    """
    Ok so the overloads need to account for creating a new index init(of which there are 2 of these I'm aware of so far), and then when you're accessing an existing index
    So the pinecone client has a has_index method, list_index, get_index details, and you're supposed to target by host

    """
    @overload
    def __init__(
        self,
        index_name: str,
        collection_name: str,
        embedding_model,
        api_key: Optional[str] = os.getenv("PINECONE_API_KEY"),
        *
        cloud : str,
        region : str,
        embedding_field_map : dict[str,str],
    ): ...

    @overload
    def __init__(
        self,
        index_name: str,
        collection_name: str,
        embedding_model,
        api_key: Optional[str] = os.getenv("PINECONE_API_KEY"),
    ): ...

    @overload
    def __init__(
        self,
        index_name: str,
        collection_name: str,
        embedding_model,
        api_key: Optional[str] = os.getenv("PINECONE_API_KEY"),
        *
        cloud : str,
        region : str,
        vector_type : str,
        dimension: int,
        metric : Metric,
        host: Optional[str] = None,
        proxy_url: Optional[str] = None,
        proxy_headers: Optional[Dict[str, str]] = None,
        ssl_ca_certs: Optional[str] = None,
        ssl_verify: Optional[bool] = None,
        additional_headers: Optional[Dict[str, str]] = None,
        pool_threads: Optional[int] = None,
        **kwargs: Any,
    ): ...
        
    @overload
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
            index_name
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

    @overload
    def upsert(
        self,
        content: Chunk | str,
        batch_size: Optional[int] = None,
    ) -> str: ...

    @overload
    def upsert(
        self,
        content: list[Chunk] | list[str],
        batch_size: Optional[int] = None,
    ) -> list[str]: ...

    def upsert(
        self,
        content: OneOrMany[Chunk] | OneOrMany[str],
        batch_size: Optional[int] = None,
    ) -> OneOrMany[str]:
        """Insert or update a batch of vectors into the store.

        The implementation may accept either a list of :class:`Chunk` instances
        (which include metadata and optional document ids) or a list of raw
        strings. Implementations should generate and return stable identifiers
        for the inserted vectors.

        Args:
            content: A singular or list of chunks or strings to add to vector store.
            batch_size: Optional batch size for upserting to Pinecone.

        Returns:
            A singular or list of string ids for the upserted vectors.
        """
        # Normalize input to list
        if isinstance(content, (str, Chunk)):
            content_list = [content]
        else:
            content_list = list(content)

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
                    vector = self.__class__.Vector(
                        str(id), values, metadata=chunk.metadata
                    )  # TODO fix typing of values and possibly metadata
                    vectors.append(vector)

        self._collection.upsert(vectors, self._collection_name, batch_size=batch_size)

        # Return in same shape as input (OneOrMany)
        return ids if len(ids) > 1 else ids[0] if ids else []

    def fetch(
        self,
        ids: OneOrMany[str],
    ) -> FetchResponse:
        """Fetch vectors for the given identifiers.

        Args:
            ids: A singular or list of vector ids to retrieve.

        Returns:
            A :class:`FetchResponse` containing the results in the same order
            as the requested ids.
        """
        # Normalize ids to list
        if isinstance(ids, str):
            ids_list = [ids]
        else:
            ids_list = list(ids)

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
                # TODO Check that this covers edge case if we empty the metadata?

            else:
                raise Exception  # TODO Fix this control logic here
            responses.append(FetchResult(id, content, vec, document, metadata))

        return responses

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
            response = self._collection.search(
                namespace=self._collection_name, query=queries, rerank=rerank
            )
        else:
            # query is what you would use for vector

            vectors = self._embedding_function(queries)
            results = []
            for vec in vectors:
                results = self._collection.query(
                    top_k=top_k,
                    vector=vec,
                    namespace=self._collection_name,
                    include_values=include_values,
                    include_metadata=include_metadata,
                )

    # This returns dict pinecone returns that other libs don't so inconsistency on return type but I think we let it be
    def delete(
        self,
        ids: OneOrMany[str],
        where: Optional[dict[str, Any]] = None,
    ) -> None:
        """Remove vectors from the store by id or metadata filter.

        Args:
            ids: Optional list of ids to remove.
            where: Optional metadata filter to delete matching vectors.
        """
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

    def count(self) -> int:
        """Return the total number of vectors stored in the collection.

        Returns:
            The total count of indexed vectors.
        """
        return self._collection.describe_index_stats()["total_vector_count"]
