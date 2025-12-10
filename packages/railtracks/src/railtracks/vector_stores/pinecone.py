import os
from typing import Optional, Literal, overload, Union, TypeVar, TYPE_CHECKING, Any
from enum import Enum
from copy import deepcopy
from uuid import uuid4

from .chunking.base_chunker import Chunk
from .vector_store_base import (
    FetchResponse,
    FetchResult,
    MetadataKeys,
    Fields,
    Metric,
    SearchResponse,
    SearchResult,
    VectorStore,
)


if TYPE_CHECKING:
    from pinecone import SearchQuery

DEFAULT = "__default__"

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
                cls._SearchQuery = SearchQuery
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
                self._has_integrated_model = False
            
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
                self._has_integrated_model = True
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
                        self._has_integrated_model = True
                    else:
                        self._has_integrated_model = False
                else:
                    raise ValueError("Pinecone returned a host that is not a string")
            else:
                indexes = self._pc.list_indexes()
                raise ValueError(f"You have provided an collection name that does not exist.\n the available indexes are {indexes}")

        else:
            raise ValueError("Incorrect pass of parameters please see docs to see valid combination of parameters")
        
        self._is_dense = embedding_model(["test"])[0] == list

    @overload
    def upsert(self, content: Chunk | str) -> str: ...

    @overload
    def upsert(self, content: list[Chunk | str]) -> list[str]: ... #Not strict typing here

    def upsert(self, content: OneOrMany[Chunk | str]) -> OneOrMany[str]:
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
        Vector = self._Vector

        is_many, content = self._one_or_many(content)

        for item in content:
            if isinstance(item, Chunk):
                id = item.id
                embedding = self._embedding_model([item.content])[0]
                metadata = item.metadata
                metadata[MetadataKeys.CONTENT] = item.content
                if item.document:
                    metadata[MetadataKeys.DOCUMENT] = item.document

            else:
                id = str(uuid4())
                embedding = self._embedding_model([item])[0]
                metadata = {MetadataKeys.CONTENT: item}

            ids.append(id)
            if isinstance(embedding, list):
                vectors.append(Vector(
                    id=id,
                    values=embedding,
                    metadata=metadata
                ))
            else:
                vectors.append(Vector(
                    id=id,
                    sparse_values=embedding,
                    metadata=metadata
                ))

        self._collection.upsert(
            namespace=DEFAULT,
            vectors=vectors,
            batch_size=len(vectors)
        )
        return ids if is_many else ids[0]
    

    @overload
    def fetch(
        self,
        *,
        ids: OneOrMany[str],
        include: Optional[list[str]] = None,
    ) -> FetchResponse: ...

    @overload
    def fetch(
        self,
        *,
        ids: OneOrMany[str],
        where: Optional[dict[str, str]] = None,
        where_document: Optional[dict[str, str]] = None,
        include: Optional[list[str]] = None,
    ) -> FetchResponse: ...

    @overload
    def fetch(
        self,
        *,
        where: Optional[dict[str, str]] = None,
        limit: Optional[int] = None,
        where_document: Optional[dict[str, str]] = None,
        include: Optional[list[str]] = None,
    ) -> FetchResponse: ...

    def fetch(
        self,
        *,
        ids: Optional[OneOrMany[str]] = None,
        where: Optional[dict[str, str]] = None,
        limit: Optional[int] = None,
        where_document: Optional[dict[str, str]] = None,
        include: Optional[list[str]] = None,
    ) -> FetchResponse:
        """Fetch a set of vectors and their metadata from the collection. This can
        be used to retrieve vectors by id, by id with a metadata filter, or by
        just a metadata filter.

        Args:
            ids: Optional list of ids or singular id to fetch.
            where: Optional metadata filter.
            limit: Optiuonal Result limit for pagination.
            where_document: Optional document-based filter.
            Include: Optional Fields to include in the response. Defaults to all.

        Returns:
            FetchResponse: A list-like container of :class:`FetchResult`.

        Raises:
            ValueError: If the response does not contain required fields.
        """
        results = FetchResponse()
        filter = self._make_filter(where=where, where_document=where_document)
        if include is None:
            include = [Fields.VECTOR, Fields.DOCUMENT, Fields.METADATA]

        if isinstance(ids, str):
            ids = [ids]

        #Get responses from pinecone
        if ids is not None:
            responses = self._collection.fetch(
                namespace=DEFAULT,
                ids = ids,
            )
            if filter is not None:
                responses = self._filter_by_metadata(responses, where, where_document)

        elif filter is not None:
            responses = self._collection.fetch_by_metadata(
                namespace=DEFAULT,
                filter = filter,
                limit = limit
            )
        
        else:
            raise ValueError("Either ids or where/where_document must be provided to fetch.")
            
        for response in responses["vectors"]:
            extracted_fields = self._extract_fetch_result_fields(responses["vectors"][response], include)
            results.append(self._make_fetch_result(extracted_fields))

        return results

    @overload
    def search(
        self,
        querys: Chunk | str,
        top_k: int = 10,
        where: Optional[dict[str, str]] = None,
        where_document: Optional[dict[str, str]] = None,
        include: Optional[list[str]] = None,
    ) -> SearchResponse: ...

    @overload
    def search(
        self,
        querys: list[Chunk | str],
        top_k: int = 10,
        where: Optional[dict[str, str]] = None,
        where_document: Optional[dict[str, str]] = None,
        include: Optional[list[str]] = None,
    ) -> list[SearchResponse]: ...

    def search(  # noqa: C901
        self,
        querys: OneOrMany[Chunk | str],
        top_k: int = 10,
        where: Optional[dict[str, str]] = None,
        where_document: Optional[dict[str, str]] = None,
        include: Optional[list[str]] = None,
    ) -> OneOrMany[SearchResponse]:
        """Run a similarity search for the provided query texts.

        Args:
            query: A list of query chunks/strings or singular chunk/string to search for.
            ids: Optional list of ids or singular id to restrict the search to.
            top_k: Number of hits to return per query.
            where: Optional metadata filter to apply.
            where_document: Optional document filter to apply.
            include: Fields to include in the response.

        Returns:
            A list of :class:`SearchResponse` objects (one per query).

        Raises:
            ValueError: If expected fields are missing from the response.
        """
        
        #Deal with one or many
        is_many, querys = self._one_or_many(querys)
        
        #Map railtracks filter to pinecone filter
        filter = self._make_filter(where=where, where_document=where_document)
        
        #Format include from railtracks Fields to pinecone fields for pinecone use
        include_fields = self._format_include_fields(include)

        #Default include all fields for internal use
        if include is None:
            include = [Fields.DISTANCE, Fields.VECTOR, Fields.DOCUMENT, Fields.METADATA]

        answer: list[SearchResponse] = []
        
        if self._has_integrated_model:
            for query in querys:
                    results = self._collection.search(
                        namespace=DEFAULT,
                        query=self._SearchQuery(
                        inputs={"text" : query} if isinstance(query, str) else {"text" : query.content},
                        top_k=top_k,
                        filter=filter #Will want to deal with different filtering for query vs search later
                    ),
                    fields=include_fields
                )
                
                    search_response = SearchResponse()

                    #Weird Pinecone format here
                    for result in results["result"]["hits"]:
                        fields = self._extract_search_result_fields(include, result)
                        search_result = self._make_search_result(fields)
                        search_response.append(search_result)
                        
                    answer.append(search_response)
        
        else:
            for query in querys:
                query_embedding = self._embedding_model([query])[0] if isinstance(query, str) else self._embedding_model([query.content])[0]
                results = self._collection.query(
                    top_k=top_k,
                    vector=query_embedding if self._is_dense else None,
                    sparse_vector=query_embedding if not self._is_dense else None,
                    namespace=DEFAULT,
                    filter=filter,
                    include_metadata=True,
                    include_values=Fields.VECTOR in include,
                )

                search_response = SearchResponse()
                for result in results["matches"]:
                    fields = self._extract_query_result_fields(include, result)
                    search_result = self._make_search_result(fields)
                    search_response.append(search_result)
                
                answer.append(search_response)

        return answer if is_many else answer[0]

    def delete(
        self,
        ids: OneOrMany[str],
        delete_all : Optional[bool] = None,
        where: Optional[dict[str, str]] = None,
        where_document: Optional[dict[str, str]] = None,
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

        filter = self._make_filter(where=where, where_document=where_document)

        self._collection.delete(
            ids=ids,
            delete_all=delete_all,
            filter=filter,
        )

    def count(self) -> int:
        """"Return the total number of vectors stored in the collection."""

        return self._collection.describe_index_stats()["total_vector_count"]
        

    #TODO need to make sure that the filtering is the way it works in pinecone. AKA add mapping. Also polish the if statements
    def _make_filter(self, where : Optional[dict[str, str]], where_document : Optional[dict[str, str]]) -> dict[str, str] | None:
        if not where and not where_document:
            return None
        elif where and not where_document:
            return dict(where)
        elif not where and where_document:
            return dict(where_document)
        elif where and where_document:
            filter = dict(where)
            for key in where_document:
                filter[key] = where_document[key]
            
            return filter
        else:
            raise ValueError("where and where_document must be None or a dict[str, str]")
        
    def _extract_search_result_fields(self, include : list[str], result : dict[str, Any]) -> dict[str, Any]:
        """Extract fields from pinecone search result into railtracks format
            This function assumes that all result metadata fields are to be extracted because of Pinecone's structure
            All magic strings are magic strings from Pinecone's search result format

            Args:
                include: List of Fields or str requested to be included
                result: Pinecone search result dict

            Returns:
                dict[str, Any]: Extracted fields in railtracks format

            
        """
        extracted_fields = {}
        #Mandatory fields
        extracted_fields["id"] = result["_id"]
        extracted_fields[MetadataKeys.CONTENT] = result["fields"][MetadataKeys.CONTENT]
        
        #Optional fields
        extracted_fields[Fields.DISTANCE] = result["_score"] if Fields.DISTANCE in include else None
        extracted_fields[Fields.DOCUMENT] = result["fields"][MetadataKeys.DOCUMENT] if Fields.DOCUMENT in include else None
        extracted_fields[Fields.METADATA] = {}

        #Get vector using fetch since pinecone cannot return it in search
        if Fields.VECTOR in include:
            fetched = self.fetch(ids=[result["_id"]])[0]
            extracted_fields[Fields.VECTOR] = fetched.vector
        else:
            extracted_fields[Fields.VECTOR] = None

        #Because Search Result fields are all in "fields" key instead of returning metadata we need to loop
        for metadata in result["fields"]:
            if metadata == MetadataKeys.CONTENT or metadata == MetadataKeys.DOCUMENT:
                pass
            else:
                #This trusts that Pinecone will only return requested metadata fields but could probably use a check
                extracted_fields[Fields.METADATA][metadata] = result["fields"][metadata]
        
        return extracted_fields
    
    #Different function for query result because of different field names
    def _extract_query_result_fields(self, include : list[str ], result : dict[str, Any]) -> dict[str, Any]:
        """Extract fields from pinecone search result into railtracks format
            This function assumes that all result metadata fields are returned
            because of Pinecone's structure. Therefore it uses include to decide what 
            metadata to extract.

            All magic strings are magic strings from Pinecone's search result format
            
            Args:
                include: List of Fields or str requested to be included
                result: Pinecone search result dict

            Returns:
                dict[str, Any]: Extracted fields in railtracks format
        """

        extracted_fields = {}
        #Mandatory fields
        extracted_fields["id"] = result["id"]
        extracted_fields[MetadataKeys.CONTENT] = result["metadata"][MetadataKeys.CONTENT]
        
        #Optional fields
        extracted_fields[Fields.DISTANCE] = result["score"] if Fields.DISTANCE in include else None
        extracted_fields[Fields.DOCUMENT] = result["metadata"][MetadataKeys.DOCUMENT] if Fields.DOCUMENT in include else None

        #Optional Vector deals with both dense and sparse
        if Fields.VECTOR in include:
            extracted_fields[Fields.VECTOR] = result["values"] if self._is_dense else result["sparseValues"]
        else:
            extracted_fields[Fields.VECTOR] = None

        if Fields.METADATA in include:
            extracted_fields[Fields.METADATA] = dict(result["metadata"])
            extracted_fields[Fields.METADATA].pop(MetadataKeys.CONTENT)
            extracted_fields[Fields.METADATA].pop(MetadataKeys.DOCUMENT, None)
        
        else:
            extracted_fields[Fields.METADATA] = {}
            for field in include:
                if not isinstance(field, Fields):
                    extracted_fields[Fields.METADATA][field] = result["metadata"][field] #Assumes that if a field is requested it exists in metadata. Should add error handling here

            return extracted_fields
        
    def _extract_fetch_result_fields(self, result : dict[str, Any], include : list[str]) -> dict[str, Any]:
        """Extract fields from pinecone fetch result into railtracks format
            This function assumes that all result metadata fields are returned
            because of Pinecone's structure. Therefore it uses include to decide what 
            metadata to extract.

            All magic strings are magic strings from Pinecone's search result format
            
            Args:
                include: List of Fields or str requested to be included
                result: Pinecone search result dict

            Returns:
                dict[str, Any]: Extracted fields in railtracks format
        """

        extracted_fields = {}
        #Mandatory fields
        extracted_fields["id"] = result["id"]
        extracted_fields[MetadataKeys.CONTENT] = result["metadata"][MetadataKeys.CONTENT]
        
        #Optional fields
        extracted_fields[Fields.DOCUMENT] = result["metadata"][MetadataKeys.DOCUMENT] if Fields.DOCUMENT in include else None

        #Optional Vector deals with both dense and sparse
        if Fields.VECTOR in include:
            extracted_fields[Fields.VECTOR] = result["values"] if self._is_dense else result["sparseValues"]
        else:
            extracted_fields[Fields.VECTOR] = None

        if Fields.METADATA in include:
            extracted_fields[Fields.METADATA] = dict(result["metadata"])
            extracted_fields[Fields.METADATA].pop(MetadataKeys.CONTENT)
            extracted_fields[Fields.METADATA].pop(MetadataKeys.DOCUMENT, None)
        
        else:
            extracted_fields[Fields.METADATA] = {}
            for field in include:
                if not isinstance(field, Fields):
                    extracted_fields[Fields.METADATA][field] = result["metadata"][field] #Assumes that if a field is requested it exists in metadata. Should add error handling here

        return extracted_fields
    
    def _make_search_result(self, result : dict[str, Any]) -> SearchResult:
        return SearchResult(
            id=result["id"],
            distance=result[Fields.DISTANCE],
            content=result[MetadataKeys.CONTENT],
            vector=result[Fields.VECTOR],
            document=result[Fields.DOCUMENT],
            metadata=result[Fields.METADATA],
        )
    
    def _make_fetch_result(self, result : dict[str, Any]) -> FetchResult:
        return FetchResult(
            id=result["id"],
            content=result[MetadataKeys.CONTENT],
            vector=result[Fields.VECTOR],
            document=result[Fields.DOCUMENT],
            metadata=result[Fields.METADATA],
        )
    
    def _filter_by_metadata(self, responses, where : Optional[dict[str,str]], where_document : Optional[dict[str, str]]):
        #Todo implement filtering here if needed
        ...

    def _format_include_fields(self, include: Optional[list[ Fields | str]]) -> list[str]:
        formatted_include = [MetadataKeys.CONTENT.value]

        if include:
            if Fields.NOTHING in include:
                if len(include) > 1:
                    raise ValueError("If Fields.NOTHING is specified no other fields can be requested")
            elif Fields.METADATA in include:
                formatted_include = ["*"] #Pinecone syntax for all metadata
            else:
                if Fields.DOCUMENT in include:
                    formatted_include.append(MetadataKeys.DOCUMENT.value)

                for field in include:
                    if not isinstance(field, Fields):
                        formatted_include.append(field)
                
        else:
            formatted_include = ["*"] #Pinecone syntax to Default to all metadata if nothing is specified

        return formatted_include