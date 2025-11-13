from __future__ import annotations
from typing import TYPE_CHECKING, List, Optional, Callable
from copy import deepcopy
from .vector_store import VectorStore, Chunk, SearchResponse, FetchResponse, FetchResult, SearchResult, Document, MetadataKeys
from uuid import uuid4
import numpy as np
if TYPE_CHECKING:
    from chromadb.base_types import Where, WhereDocument
    from chromadb.api.types import Include

CONTENT = MetadataKeys.CONTENT.value

class ChromaVectorStore(VectorStore):
    """ChromaDB implementation of VectorStore."""

    @classmethod
    def class_init(cls, path, host, port):
        if not hasattr(cls, "_chroma"):
            #First object initialized so import Chroma and connect create temporary, persistent or http client. Don't currently support chroma cloud client
            try:
                import chromadb
                if path:
                    cls._chroma = chromadb.PersistentClient(path=path)
                elif host and port:
                    cls._chroma = chromadb.HttpClient(host=host, port=port) #Currently this does not provide the extra asycn features that comes with this
                else:
                    cls._chroma = chromadb.EphemeralClient()
            except ImportError:
                raise ImportError("Chroma package is not installed. Please install railtracks[chroma].")
    
    def __init__(
        self,
        collection_name: str,
        embedding_function: Callable[[List[str]], List[List[float]]],
        path: Optional[str] = None,
        host: Optional[str] = None,
        port: Optional[int] = None,
    ):
        self._collection_name = collection_name
        self._embedding_function = embedding_function

        ChromaVectorStore.class_init(path, host, port)
        self._collection = self._chroma.get_or_create_collection(
            collection_name,
        )

    #In future should have our own chunking service so we can accept documents and chunk for users
    #TODO cross reference
    def upsert(
        self,
        content : List[Chunk] | List[str]
    ) -> List[str]:
        
        
        ids = []
        embeddings = []
        metadatas = []
        documents = []

        for item in content:
            id = uuid4().int
            ids.append(str(id))

            if isinstance(item, Chunk):
                embedding = self._embedding_function([item.content])[0]
                metadata = item.metadata
                metadata[CONTENT] = item.content
                documents.append(item.document)

            else:
                embedding = self._embedding_function([item])[0]
                metadata = {CONTENT: item}
                documents.append(None)

            embeddings.append(embedding)
            metadatas.append(metadata)

        self._collection.upsert(
            ids=ids,
            embeddings=embeddings,
            metadatas=metadatas,
            documents=documents
            )
        return ids

    #TODO cross reference
    def fetch(
            self, 
            ids: Optional[List[str]]  = None,
            where: Optional[Where] = None,
            limit: Optional[int] = None,
            offset: Optional[int] = None,
            where_document: Optional[WhereDocument] = None,
            ) -> FetchResponse:
        
        results = FetchResponse()
        #currently we ignore Include and assume the left it as default
        responses = self._collection.get(
            ids,
            where,
            limit,
            offset,
            where_document,
            include = ["embeddings", "metadatas", "documents"])
        
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
                raise ValueError("Content was not initialized in vector. Please create an issue")
            
            metadata.pop(CONTENT)
            results.append(FetchResult(
                id=id,
                content=content, 
                vector=list(embeddings[i]),
                document=documents[i],
                metadata=metadata
                )
            )
            
        return results
    
    #There is support for other types of query modalities but for now just list of strings
    #Should Probably add support for Chunks as well
    #TODO cross reference and fix typing plust batch querys problems. Could be an issue with the large nested nature of this
    def search(
        self,
        query: List[str], 
        ids: Optional[List[str]] = None,
        n_results: int = 10,
        where: Optional[Where] = None,
        where_document: Optional[WhereDocument] = None,
        include: Include = [
            "metadatas",
            "embeddings",
            "documents",
            "distances",
        ],
    ) -> List[SearchResponse]:
        query_embeddings = self._embedding_function(query)
        results = self._collection.query(
            query_embeddings=list(query_embeddings),
            ids=ids,
            n_results=n_results,
            where=where,
            where_document=where_document,
            include=include
        )
        answer = []
        for query_idx, query_response in enumerate(results["ids"]):
            search_response = SearchResponse()
            for id_idx, id in enumerate(query_response):

                if not (distance := results.get("distances")):
                    raise ValueError("Distance not found in search results.")
                if not (vector := results.get("embeddings")):
                    raise ValueError("Vector not found in search results.")
                if not (document := results.get("documents")):
                    raise ValueError("Document not found in search results.")
                if not (metadatas := results.get("metadatas")):
                    raise ValueError("Metadata not found in search results.")

                distance = distance[query_idx][id_idx]
                vector = list(vector[query_idx][id_idx])
                document = document[query_idx][id_idx]
                metadata = dict(deepcopy(metadatas[query_idx][id_idx]))

                if not (content := metadata.get(CONTENT)) or not isinstance(content, str):
                    raise ValueError("Content was not initialized in vector. Please create an issue")
        
                metadata.pop(CONTENT)

                search_response.append(SearchResult(
                    id=id,
                    distance=distance,
                    content=content,
                    vector=vector,
                    document=document, #Chroma document is just a str
                    metadata = metadata
                    )
                )
            answer.append(search_response)

        return answer
    
    #TODO Cross-reference and then update the where filtering using unified filter
    def delete(
        self,
        ids: Optional[List[str]] = None,
        where: Optional[Where] = None,
        where_document: Optional[WhereDocument] = None,
    ):
        self._collection.delete(
            ids=ids,
            where=where,
            where_document=where_document,
        )
    
    def count(self) -> int:
        return self._collection.count()