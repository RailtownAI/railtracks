from __future__ import annotations

from copy import deepcopy
from typing import TYPE_CHECKING, Callable, Optional, TypeVar, Union, overload
from uuid import uuid4

from .chunking.base_chunker import Chunk
from .vector_store_base import (
    FetchResponse,
    FetchResult,
    MetadataKeys,
    SearchResponse,
    SearchResult,
    VectorStore,
)

if TYPE_CHECKING:
    from chromadb.api.types import Include
    from chromadb.base_types import Where, WhereDocument


CONTENT = MetadataKeys.CONTENT.value

T = TypeVar("T")

OneOrMany = Union[T, list[T]]


class ChromaVectorStore(VectorStore):
    """ChromaDB-backed implementation of :class:`VectorStore`.

    This class wraps a Chroma collection and translates between Chroma's
    API and the project's neutral types. The implementation currently
    supports upserting lists of either :class:`Chunk` or strings and
    querying by text strings.
    """

    @classmethod
    def class_init(
        cls, path: Optional[str], host: Optional[str], port: Optional[int]
    ) -> None:
        """Lazily initialize the shared Chroma client.

        This method performs an optional import of Chroma and creates a
        persistent, HTTP or ephemeral client depending on the parameters.

        Args:
            path: Filesystem path for a persistent client (optional).
            host: Hostname for an HTTP client (optional).
            port: Port for an HTTP client (optional).

        Raises:
            ImportError: If the `chromadb` package is not installed.
        """
        if not hasattr(cls, "_chroma"):
            try:
                import chromadb

                # Provide just a path for local store
                if path and not host and not port:
                    cls._chroma = chromadb.PersistentClient(path=path)
                # Provide just a host and port for http store
                elif not path and host and port:
                    cls._chroma = chromadb.HttpClient(host=host, port=port)
                # Provide nothing for temporary store
                elif not path and not host and not port:
                    cls._chroma = chromadb.EphemeralClient()
                else:
                    raise ValueError(
                        "Invalid combination of path, host, and port for Chroma client."
                    )
            except ImportError:
                raise ImportError(
                    "Chroma package is not installed. Please install railtracks[chroma]."
                )

    @overload
    def __init__(
        self,
        collection_name: str,
        embedding_function: Callable[[list[str]], list[list[float]]],
        *,
        path: str,
    ) -> None: ...

    @overload
    def __init__(
        self,
        collection_name: str,
        embedding_function: Callable[[list[str]], list[list[float]]],
        *,
        host: str,
        port: int,
    ) -> None: ...

    @overload
    def __init__(
        self,
        collection_name: str,
        embedding_function: Callable[[list[str]], list[list[float]]],
    ) -> None: ...

    def __init__(
        self,
        collection_name: str,
        embedding_function: Callable[[list[str]], list[list[float]]],
        path: Optional[str] = None,
        host: Optional[str] = None,
        port: Optional[int] = None,
    ):
        """Create a ChromaVectorStore instance.

        Args:
            collection_name: Name of the Chroma collection to use or create.
            embedding_function: Callable that maps a list of strings to a list
                of embedding vectors.
            path: Optional path for persistent Chroma storage.
            host: Optional HTTP host for remote Chroma.
            port: Optional HTTP port for remote Chroma.
        """
        self._collection_name = collection_name
        self._embedding_function = embedding_function

        ChromaVectorStore.class_init(path, host, port)
        self._collection = self._chroma.get_or_create_collection(collection_name)

    # In future should have our own chunking service so we can accept documents for users
    @overload
    def upsert(self, content: Chunk | str) -> str: ...

    @overload
    def upsert(self, content: list[Chunk] | list[str]) -> list[str]: ...

    def upsert(self, content: OneOrMany[Chunk] | OneOrMany[str]) -> OneOrMany[str]:
        """Upsert a batch of chunks or raw strings into the collection.

        The method accepts a list of :class:`Chunk` instances or plain strings.
        Each element is embedded via ``embedding_function`` and stored along
        with metadata that always contains the original content under the
        key defined in :data:`CONTENT`.

        Args:
            content: List of or singular chunks or strings to upsert.

        Returns:
            OneOrMany[str]: Generated ids for the inserted items.
        """
        ids = []
        embeddings = []
        metadatas = []
        documents = []
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
                embedding = self._embedding_function([item.content])[0]
                metadata = item.metadata
                metadata[CONTENT] = item.content
                documents.append(item.document)

            else:
                id = str(uuid4())
                embedding = self._embedding_function([item])[0]
                metadata = {CONTENT: item}
                documents.append(None)

            ids.append(id)
            embeddings.append(embedding)
            metadatas.append(metadata)

        self._collection.upsert(
            ids=ids, embeddings=embeddings, metadatas=metadatas, documents=documents
        )
        return ids if is_many else ids[0]

    def fetch(
        self,
        ids: Optional[OneOrMany[str]] = None,
        where: Optional[Where] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
        where_document: Optional[WhereDocument] = None,
    ) -> FetchResponse:
        """Fetch a set of vectors and their metadata from the collection.

        Args:
            ids: Optional list of ids or singular id to fetch.
            where: Optional metadata filter.
            limit: Result limit for pagination.
            offset: Result offset for pagination.
            where_document: Optional document-based filter.

        Returns:
            FetchResponse: A list-like container of :class:`FetchResult`.

        Raises:
            ValueError: If the Chroma response does not contain required fields.
        """
        results = FetchResponse()
        # currently we ignore Include and assume the default
        responses = self._collection.get(
            ids,
            where,
            limit,
            offset,
            where_document,
            include=["embeddings", "metadatas", "documents"],
        )

        embeddings = responses.get("embeddings")
        if embeddings is None:
            raise ValueError("Embeddings were not found in fetch response.")
        documents = responses.get("documents")
        if documents is None:
            raise ValueError("Documents were not found in fetch response.")
        metadatas = responses.get("metadatas")
        if metadatas is None:
            raise ValueError("Metadatas were not found in fetch response.")

        for i, response in enumerate(responses["ids"]):
            id = response

            metadata = dict(deepcopy(metadatas[i]))
            if not (content := metadata.get(CONTENT)) or not isinstance(content, str):
                raise ValueError(
                    "Content was not initialized in vector. Please create an issue"
                )

            metadata.pop(CONTENT)
            results.append(
                FetchResult(
                    id=id,
                    content=content,
                    vector=list(embeddings[i]),
                    document=documents[i],
                    metadata=metadata,
                )
            )

        return results

    # There is support for other types of query modalities but for now just list of strings
    # Should Probably add support for Chunks as well
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
            query: A list of query strings or singular string to search for.
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

        query_embeddings = self._embedding_function(query)
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

        self._collection.delete(
            ids=ids,
            where=where,
            where_document=where_document,
        )

    def count(self) -> int:
        """Return the total number of vectors stored in the collection."""
        return self._collection.count()
