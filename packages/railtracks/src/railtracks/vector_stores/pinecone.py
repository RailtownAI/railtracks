import os
from typing import Optional, Literal, overload, Union, TypeVar
from copy import deepcopy
from uuid import uuid4

from .vector_store_base import (
    Chunk,
    FetchResponse,
    FetchResult,
    MetadataKeys,
    Metric,
    SearchResponse,
    SearchResult,
    VectorStore,
)


CONTENT = MetadataKeys.CONTENT.value
DOCUMENT = MetadataKeys.DOCUMENT.value

T = TypeVar("T")

OneOrMany = Union[T, list[T]]

class PineconeVectorStore(VectorStore):
    """Pinecone implementation of VectorStore."""

    @classmethod
    def class_init(
        cls,
        api_key: Optional[str] = os.getenv("PINECONE_API_KEY"),

    ):
        if not hasattr(cls, "_pc"):
            try:
                from pinecone import Pinecone, Vector, ServerlessSpec
                from pinecone.inference.models.index_embed import IndexEmbed

                # store imports on the class so other methods can reference them
                cls._Vector = Vector
                cls._ServerlessSpec = ServerlessSpec
                cls._IndexEmbed = IndexEmbed
                cls._pc = Pinecone(api_key=api_key)

            except ImportError:
                raise ImportError(
                    "Pinecone package is not installed. Please install railtracks[pinecone]."
                )
            

    @overload
    def __init__(
        self,
        collection_name: str,
        embedding_model,
        api_key: Optional[str] = os.getenv("PINECONE_API_KEY"),
        *,
        vector_type,
        dimension,
        metric,
        cloud,
        region,
        deletion_protection
    ): ...

    @overload
    def __init__(
        self,
        collection_name: str,
        embedding_model,
        api_key: Optional[str] = os.getenv("PINECONE_API_KEY"),
        *,
        cloud,
        region,
        field_map,
        deletion_protection
    ): ...

    @overload
    def __init__(
        self,
        collection_name: str,
        embedding_model,
        api_key: Optional[str] = os.getenv("PINECONE_API_KEY"),
    ): ...
        
    def __init__(
        self,
        collection_name: str,
        embedding_model,
        api_key: Optional[str] = os.getenv("PINECONE_API_KEY"),
        *,
        vector_type : Optional[str]=None,
        dimension: Optional[int]=None,
        metric: Optional[Metric] = None,
        region : Optional[str] = None,
        cloud : Optional[str] = None,
        field_map : Optional[dict[str,str]] = None,
        deletion_protection : Optional[Literal["enabled", "disabled"]] = "disabled",
    ):
        
        PineconeVectorStore.class_init(
            api_key,
        )
        super().__init__(collection_name, embedding_model)

        #Create a manual index
        if vector_type and dimension and metric and cloud and region and deletion_protection and field_map is None:
            host = self._pc.create_index(
                name=collection_name,
                vector_type=vector_type,
                dimension=dimension, #It would be a good idea to get the dimension for the user instead of making them pass it to us
                metric=metric,
                spec=self._ServerlessSpec(
                    cloud=cloud,
                    region=region
                ),
                deletion_protection=deletion_protection
            )["host"]
            
            if isinstance(host, str):
                self._collection = self._pc.Index(host=host)
                self.has_integrated_model = False
            
            else:
                raise ValueError("Pinecone returned a host that is not a string")
            
        #create and index with integrated embedding model
        elif cloud and region and field_map and deletion_protection and vector_type is None and dimension is None and metric is None:
            host = self._pc.create_index_for_model(
                name=collection_name,
                cloud=cloud,
                region=region,
                embed=self._IndexEmbed( # This should be checked out because Pinecone docs has this parameter as a dict but it is currently typed as a IndexEmbed...
                    model=embedding_model,
                    field_map=field_map
                ),
                deletion_protection=deletion_protection
            )["host"]

            if isinstance(host, str):
                self._collection = self._pc.Index(host=host)
                self.has_integrated_model = True
            else:
                raise ValueError("Pinecone returned a host that is not a string")
            
        #Connect to index
        elif vector_type is None and dimension is None and metric is None and region is None and cloud is None and field_map is None:
            if self._pc.has_index(collection_name):
                index_details = self._pc.describe_index(collection_name)
                host = index_details["host"]
                if isinstance(host, str):
                    self._collection = self._pc.Index(host=host)
                    if "embed" in index_details:
                        self.has_integrated_model = True
                    else:
                        self.has_integrated_model = False
                else:
                    raise ValueError("Pinecone returned a host that is not a string")
            else:
                indexes = self._pc.list_indexes()
                raise ValueError(f"You have provided an collection name that does not exist.\n the available indexes are {indexes}")

        else:
            raise ValueError("Incorrect pass of parameters please see docs to see valid combination of parameters")

    @overload
    def upsert(self, content: Chunk | str) -> str: ...

    @overload
    def upsert(self, content: list[Chunk] | list[str]) -> list[str]: ...

    def upsert(self, content: OneOrMany[Chunk] | OneOrMany[str]) -> OneOrMany[str]:
        """Upsert a batch of chunks or raw strings into the collection.

        The method accepts a list of :class:`Chunk` instances or plain strings.
        Each element is embedded via ``embedding_model`` and stored along
        with metadata that always contains the original content.

        Args:
            content: List of or singular chunks or strings to upsert.

        Returns:
            OneOrMany[str]: Generated ids for the inserted items.
        """
        vectors = []
        ids = []
        Vector = type(PineconeVectorStore)._Vector

        is_many = True
        if isinstance(content, str):
            content = [content]
            is_many = False

        if isinstance(content, Chunk):
            content = [content]
            is_many = False

        for item in content:
            if isinstance(item, Chunk):
                id = item.id
                embedding = self._embedding_model([item.content])[0]
                metadata = item.metadata
                metadata[CONTENT] = item.content
                if item.document:
                    metadata[DOCUMENT] = item.document

            else:
                id = str(uuid4())
                embedding = self._embedding_model([item])[0]
                metadata = {CONTENT: item}

            ids.append(id)
            vectors.append(Vector(
                id=id,
                values=embedding,
                metadata=metadata
            ))

        self._collection.upsert(
            vectors=vectors,
            batch_size=len(vectors)
        )
        return ids if is_many else ids[0]

    def fetch(
        self,
        ids: Optional[OneOrMany[str]] = None,
        where: Optional[Where] = None,
        limit: Optional[int] = None,
        where_document: Optional[WhereDocument] = None,
    ) -> FetchResponse:
        """Fetch a set of vectors and their metadata from the collection.

        Args:
            ids: Optional list of ids or singular id to fetch.
            where: Optional metadata filter.
            limit: Result limit for pagination.

        Returns:
            FetchResponse: A list-like container of :class:`FetchResult`.

        Raises:
            ValueError: If the Chroma response does not contain required fields.
        """
        results = FetchResponse()
        # currently we ignore Include and assume the default

        if isinstance(ids, str):
            ids = [ids]

        if ids is not None and not where and not limit:
            responses = self._collection.fetch(
                ids = ids,
            )
        
        #Add in WhereDocument to this here
        elif ids is None and where:
            responses = self._collection.fetch_by_metadata(
                filter = where,
                limit = limit
            )

        else:
            raise ValueError("Incorrect parameters passed. Valid combinations include :" \
            "ids," \
            "" \
            "where," \
            "" \
            "where," \
            "limit")

        for response in responses["vectors"]:

            id = response["id"]
            embedding = response["values"]
            metadata = response["metadata"]
            if metadata is None:
                raise ValueError(f"Metadata was not found in chunk with id: {id}. Please create an issue")
            metadata = dict(deepcopy(response["metadata"]))

            document = metadata.get(DOCUMENT, None)
            content = metadata[CONTENT]
            if not (content := metadata.get(CONTENT)) or not isinstance(content, str):
                raise ValueError(
                    "Content was not initialized in chunk with id: {id}. Please create an issue"
                )

            metadata.pop(CONTENT)
            metadata.pop(DOCUMENT)

            results.append(
                FetchResult(
                    id=id,
                    content=content,
                    vector=embedding,
                    document=document,
                    metadata=metadata,
                )
            )

        return results

    @overload
    def search(
        self,
        query: Chunk | str,
        ids: Optional[str] = None,
        top_k: int = 10,
        where: Optional[Where] = None,
        where_document: Optional[WhereDocument] = None,
        include: Include = [
            "metadatas",
            "embeddings",
            "documents",
            "distances",
        ],
    ) -> SearchResponse: ...

    @overload
    def search(
        self,
        query: list[Chunk] | list[str],
        ids: Optional[list[str]] = None,
        top_k: int = 10,
        where: Optional[Where] = None,
        where_document: Optional[WhereDocument] = None,
        include: Include = [
            "metadatas",
            "embeddings",
            "documents",
            "distances",
        ],
    ) -> list[SearchResponse]: ...

    def search(  # noqa: C901
        self,
        query: OneOrMany[Chunk] | OneOrMany[str],
        ids: Optional[OneOrMany[str]] = None,
        top_k: int = 10,
        where: Optional[Where] = None,
        where_document: Optional[WhereDocument] = None,
        include: Include = [
            "metadatas",
            "embeddings",
            "documents",
            "distances",
        ],
    ) -> OneOrMany[SearchResponse]:
        """Run a similarity search for the provided query texts.

        Args:
            query: A list of query chunks/strings or singular chunk/string to search for.
            ids: Optional list of ids or singular id to restrict the search to.
            top_k: Number of hits to return per query.
            where: Optional metadata filter to apply.
            where_document: Optional document filter to apply.
            include: Fields to include in the Chroma response.

        Returns:
            A list of :class:`SearchResponse` objects (one per query).

        Raises:
            ValueError: If expected fields are missing from the Chroma response.
        """
        is_many = True
        # If a single chunk is passed in, convert to list of string
        if isinstance(query, Chunk):
            query = [query.content]
            is_many = False

        # If a single string is passed in, convert to list of string
        elif isinstance(query, str):
            query = [query]
            is_many = False

        # If list of chunks is passed in, convert to list of strings
        elif isinstance(query, list) and all(isinstance(q, Chunk) for q in query):
            query = [q.content for q in query]

        elif isinstance(query, list) and all(isinstance(q, str) for q in query):
            pass
        else:
            raise ValueError(
                "Query must be a string, Chunk, or list of strings/Chunks."
            )

        query_embeddings = self._embedding_model(query)
        results = self._collection.query(
            query_embeddings=list(query_embeddings),
            ids=ids,
            n_results=top_k,
            where=where,
            where_document=where_document,
            include=include,
        )
        answer: list[SearchResponse] = []
        for query_idx, query_response in enumerate(results["ids"]):
            search_response = SearchResponse()
            for id_idx, id in enumerate(query_response):
                if not (distance := results.get("distances")):
                    raise ValueError("Distance not found in search results.")
                elif not (vector := results.get("embeddings")):
                    raise ValueError("Vector not found in search results.")
                elif not (document := results.get("documents")):
                    raise ValueError("Document not found in search results.")
                elif not (metadatas := results.get("metadatas")):
                    raise ValueError("Metadata not found in search results.")

                distance = distance[query_idx][id_idx]
                vector = list(vector[query_idx][id_idx])
                document = document[query_idx][id_idx]
                metadata = dict(deepcopy(metadatas[query_idx][id_idx]))

                if not (content := metadata.get(CONTENT)) or not isinstance(
                    content, str
                ):
                    raise ValueError(
                        "Content was not initialized in vector. Please create an issue"
                    )

                metadata.pop(CONTENT)

                search_response.append(
                    SearchResult(
                        id=id,
                        distance=distance,
                        content=content,
                        vector=vector,
                        document=document,  # Chroma document is just a str
                        metadata=metadata,
                    )
                )
            answer.append(search_response)

        return answer if is_many else answer[0]

    def delete(
        self,
        ids: OneOrMany[str],
        delete_all : Optional[bool] = None,
        where: Optional[Where] = None,
        where_document: Optional[WhereDocument] = None,
    ):
        """
        Remove vectors from the store by id or metadata filter.
        Args:
            ids: list of ids or singular id to delete.
            where: Optional metadata filter.
            where_document: Optional document-based filter.
        """

        if isinstance(ids, str):
            ids = [ids]

        if where_document:
            if where:
                where[DOCUMENT] = where_document
            else:
                where = {DOCUMENT : where_document}

        self._collection.delete(
            ids=ids,
            delete_all=delete_all,
            filter=where,
        )

    def count(self) -> int:
        """"Return the total number of vectors stored in the collection."""
        

        return self._collection.describe_index_stats()["total_vector_count"]
