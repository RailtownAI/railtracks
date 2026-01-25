import os
from typing import Optional, Literal, overload, Union, TypeVar, TYPE_CHECKING, Any
from uuid import uuid4

from .chunking.base_chunker import Chunk
from .filter import Op, LogicOp, LeafExpr, LogicExpr, BaseExpr
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

OP_PINECONE_MAP = {
    Op.EQ : "$eq",
    Op.NE : "$ne",
    Op.GT : "$gt",
    Op.GTE : "$gte",
    Op.LT : "$lt",
    Op.LTE : "$lte",
    Op.IN : "$in",
    Op.NIN : "$nin",
}

LOGICOP_PINECONE_MAP = {
    LogicOp.AND : "$and",
    LogicOp.OR : "$or"
}

class PineconeVectorStore(VectorStore):
    """Pinecone implementation of VectorStore."""

    @classmethod
    def class_init(
        cls,
        api_key: Optional[str] = os.getenv("PINECONE_API_KEY"),

    ):
        """Initialize Pinecone class-level dependencies and configuration.

        This method sets up the Pinecone client and imports required classes
        at the class level so they can be used across all instances.

        Args:
            api_key: Optional Pinecone API key. Defaults to PINECONE_API_KEY
                environment variable.

        Raises:
            ImportError: If the Pinecone package is not installed.
        """
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
        """Initialize a Pinecone vector store instance.

        This constructor supports three modes of operation:
        1. Create a manual index with specified parameters
        2. Create an index with an integrated embedding model
        3. Connect to an existing index

        Args:
            collection_name: Name of the Pinecone index to use or create.
            embedding_model: Callable that converts strings to embeddings
                (list of floats for dense or dict for sparse vectors).
            api_key: Optional Pinecone API key. Defaults to PINECONE_API_KEY
                environment variable.
            vector_type: Optional type for vectors (e.g., 'dense'). Required
                for manual index creation.
            dimension: Optional dimension of the vectors. Required for manual
                index creation.
            metric: Optional distance metric (cosine, l2, dot). Required for
                manual index creation.
            region: Optional Pinecone region. Required for index creation.
            cloud: Optional cloud provider (e.g., 'aws', 'gcp'). Required for
                index creation.
            field_map: Optional mapping for integrated model embeddings.
                Required for integrated model index creation.
            deletion_protection: Optional deletion protection setting ('enabled'
                or 'disabled'). Defaults to 'disabled'.

        Raises:
            ImportError: If Pinecone package is not installed.
            ValueError: If invalid parameter combinations are provided or if
                the specified index does not exist.
        """
        
        PineconeVectorStore.class_init(
            api_key,
        )
        super().__init__(collection_name, embedding_model)

        #Create a manual index
        if vector_type and dimension and metric and cloud and region and deletion_protection and field_map is None:
            host = self._pc.create_index(
                name=collection_name,
                vector_type=vector_type,
                dimension=dimension,
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

        made_many, content = self._make_many(content)

        for item in content:
            if isinstance(item, Chunk):
                id = item.id
                embedding = self._embedding_model([item.content])[0]
                metadata = dict(item.metadata) if item.metadata else {}
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
        return ids[0] if made_many else ids
    

    @overload
    def fetch(
        self,
        *,
        ids: OneOrMany[str],
        include: Optional[list[str | Fields]] = None,
    ) -> FetchResponse: ...

    @overload
    def fetch(
        self,
        *,
        ids: OneOrMany[str],
        where: Optional[BaseExpr] = None,
        pinecone_where: Optional[dict[str, Any]] = None,
        include: Optional[list[str | Fields]] = None,
    ) -> FetchResponse: ...

    @overload
    def fetch(
        self,
        *,
        where: Optional[BaseExpr] = None,
        pinecone_where: Optional[dict[str, Any]] = None,
        limit: Optional[int] = None,
        include: Optional[list[str | Fields]] = None,
    ) -> FetchResponse: ...

    def fetch(
        self,
        *,
        ids: Optional[OneOrMany[str]] = None,
        where: Optional[BaseExpr] = None,
        pinecone_where: Optional[dict[str, Any]] = None,
        limit: Optional[int] = None,
        include: Optional[list[str | Fields]] = None,
    ) -> FetchResponse:
        """Fetch a set of vectors and their metadata from the collection. This can
        be used to retrieve vectors by id, by id with a metadata filter, or by
        just a metadata filter.

        Args:
            ids: Optional list of ids or singular id to fetch.
            where: Optional metadata filter using railtracks syntax.
            pinecone_where: Optional metadata filter using Pinecone syntax.
            limit: Optiuonal Result limit for pagination.
            Include: Optional Fields to include in the response. Defaults to all.

        Returns:
            FetchResponse: A list-like container of :class:`FetchResult`.

        Raises:
            ValueError: If the response does not contain required fields.
        """
        results = FetchResponse()

        if include is None:
            include = [Fields.VECTOR, Fields.DOCUMENT, Fields.METADATA]

        # Get responses from pinecone by metadata filter if provided
        if where is not None or pinecone_where is not None:
            filter = self._to_pinecone_filter(where) if where is not None else pinecone_where
            responses = self._collection.fetch_by_metadata(
                namespace=DEFAULT,
                filter = filter,
                limit = limit
            )

            #Filter responses by ids if where is provided
            if ids is not None:
                _, ids = self._make_many(ids)
                responses = self._filter_by_ids(responses, ids)

        # Get by responses from pinecone by ids if provided
        elif ids is not None:
            _, ids = self._make_many(ids)
            
            responses = self._collection.fetch(
                namespace=DEFAULT,
                ids = ids,
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
        where: Optional[BaseExpr] = None,
        pinecone_where: Optional[dict[str, str]] = None,
        include: Optional[list[str | Fields]] = None,
    ) -> SearchResponse: ...

    @overload
    def search(
        self,
        querys: list[Chunk | str],
        top_k: int = 10,
        where: Optional[BaseExpr] = None,
        pinecone_where: Optional[dict[str, str]] = None,
        include: Optional[list[str | Fields]] = None,
    ) -> list[SearchResponse]: ...

    def search(  # noqa: C901
        self,
        querys: OneOrMany[Chunk | str],
        top_k: int = 10,
        where: Optional[BaseExpr] = None,
        pinecone_where: Optional[dict[str, str]] = None,
        include: Optional[list[str | Fields]] = None,
    ) -> OneOrMany[SearchResponse]:
        """Perform a similarity search for the provided query texts.

        Args:
            querys: A singular or list of query chunks or strings to search for.
            top_k: Number of nearest neighbours to return per query.
            where: Optional metadata filter using railtracks syntax.
            pinecone_where: Optional metadata filter using Pinecone syntax.
            include: Optional list of result fields to include.

        Returns:
            A singular or list of :class:`SearchResponse` objects (one per query).
        """
        
        #Deal with one or many
        made_many, querys = self._make_many(querys)
        
        #Map railtracks filter to pinecone filter
        if where:
            filter = self._to_pinecone_filter(where)
        
        #Format include from railtracks Fields to pinecone fields for pinecone use
        include_fields = self._to_pinecone_include(include)

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
                        filter=filter or pinecone_where #Will want to deal with different filtering for query vs search later #TODO
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
                    filter=filter or pinecone_where,
                    include_metadata=True,
                    include_values=Fields.VECTOR in include,
                )

                search_response = SearchResponse()
                for result in results["matches"]:
                    fields = self._extract_query_result_fields(include, result)
                    search_result = self._make_search_result(fields)
                    search_response.append(search_result)
                
                answer.append(search_response)

        return answer[0] if made_many else answer
    
    def delete(
        self,
        ids: Optional[OneOrMany[str]] = None,
        where: Optional[BaseExpr] = None,
        pinecone_where: Optional[dict[str, Any]] = None,
        delete_all : Optional[bool] = None,
    ):
        """Remove vectors from the store by id or metadata filter.

        Args:
            ids: Optional list of ids or singular id to delete.
            where: Optional metadata filter using railtracks syntax.
            pinecone_where: Optional metadata filter using Pinecone syntax.
            delete_all: Optional boolean to delete all vectors in the collection.
        """
        if ids is not None:
            _, ids = self._make_many(ids)

        if where:
            filter = self._to_pinecone_filter(where=where)

        self._collection.delete(
            ids=ids,
            delete_all=delete_all,
            filter=filter or pinecone_where,
            namespace=DEFAULT
        )

    def count(self) -> int:
        """Return the total number of vectors stored in the collection.

        Returns:
            int: The total count of indexed vectors.
        """

        return self._collection.describe_index_stats()["total_vector_count"]
        
    def _extract_search_result_fields(self, include : list[str | Fields], result : dict[str, Any]) -> dict[str, Any]:
        """Extract fields from pinecone search result into railtracks format.

        This function assumes that all result metadata fields are to be extracted
        because of Pinecone's structure. All magic strings are from Pinecone's
        search result format.

        Args:
            include: List of Fields or str requested to be included in the result.
            result: Pinecone search result dict.

        Returns:
            dict[str, Any]: Extracted fields in railtracks format.
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
    def _extract_query_result_fields(self, include : list[str | Fields], result : dict[str, Any]) -> dict[str, Any]:
        """Extract fields from pinecone query result into railtracks format.

        This function assumes that all result metadata fields are returned
        because of Pinecone's structure. Therefore it uses include to decide what
        metadata to extract. All magic strings are from Pinecone's search result
        format.

        Args:
            include: List of Fields or str requested to be included in the result.
            result: Pinecone query result dict.

        Returns:
            dict[str, Any]: Extracted fields in railtracks format.
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
        
    def _extract_fetch_result_fields(self, result : dict[str, Any], include : list[str | Fields]) -> dict[str, Any]:
        """Extract fields from pinecone fetch result into railtracks format.

        This function assumes that all result metadata fields are returned
        because of Pinecone's structure. Therefore it uses include to decide what
        metadata to extract. All magic strings are from Pinecone's fetch result
        format.

        Args:
            result: Pinecone fetch result dict.
            include: List of Fields or str requested to be included in the result.

        Returns:
            dict[str, Any]: Extracted fields in railtracks format.
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
        """Convert a field dictionary into a SearchResult object.

        Args:
            result: Dictionary containing extracted search result fields
                including id, content, distance, vector, document, and metadata.

        Returns:
            SearchResult: Formatted search result object.
        """
        return SearchResult(
            id=result["id"],
            distance=result[Fields.DISTANCE],
            content=result[MetadataKeys.CONTENT],
            vector=result[Fields.VECTOR],
            document=result[Fields.DOCUMENT],
            metadata=result[Fields.METADATA],
        )
    
    def _make_fetch_result(self, result : dict[str, Any]) -> FetchResult:
        """Convert a field dictionary into a FetchResult object.

        Args:
            result: Dictionary containing extracted fetch result fields
                including id, content, vector, document, and metadata.

        Returns:
            FetchResult: Formatted fetch result object.
        """
        return FetchResult(
            id=result["id"],
            content=result[MetadataKeys.CONTENT],
            vector=result[Fields.VECTOR],
            document=result[Fields.DOCUMENT],
            metadata=result[Fields.METADATA],
        )
    
    def _to_pinecone_filter(self, where : BaseExpr) -> dict[str, Any]:
        """Convert railtracks filter expression to Pinecone filter format.

        Args:
            where: Railtracks filter expression.

        Returns:
            dict[str, Any]: Pinecone filter dictionary.

        Raises:
            TypeError: If where is not a valid Filter Expression.
        """

        filter = {}
        if isinstance(where, LeafExpr):
            filter[where.pred.field] = { OP_PINECONE_MAP[where.pred.op]: where.pred.value}

        elif isinstance(where, LogicExpr):
            filter_list = [] 
            for expression in where.children:
                filter = self._to_pinecone_filter(expression)
                filter_list.append(filter)
            filter = {LOGICOP_PINECONE_MAP[where.op] : filter_list}
        else:
            raise TypeError("""where provided is not a Filter Expression.
                            Either provide where with Filter Expression using Railtracks
                            or provide pinecone_filter using pinecone filtering""")
        
        return filter
    
    def _filter_by_ids(self, responses, ids : list[str], ) -> dict:
        """Filter fetch responses to only include specified ids.

        Args:
            responses: Dictionary of fetch responses with vectors key.
            ids: List of vector ids to include in the filtered response.

        Returns:
            dict: Filtered responses containing only the specified ids.
        """
        filtered_responses = {}
        for id in responses["vectors"]:
            if id in ids:
                filtered_responses[id]
        return {"vectors" : filtered_responses}

    def _to_pinecone_include(self, include: Optional[list[ Fields | str]]) -> list[str]:
        """Convert railtracks include fields to Pinecone format.

        Maps Fields enum values and custom field strings to Pinecone's
        field specification format.

        Args:
            include: Optional list of Fields enums or custom field names to include
                in results.

        Returns:
            list[str]: Formatted field list for Pinecone API.

        Raises:
            ValueError: If Fields.NOTHING is specified alongside other fields.
        """
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