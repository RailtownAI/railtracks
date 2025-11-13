from __future__ import annotations
from typing import TYPE_CHECKING, List, Literal, Any, Optional, Callable
from .vector_store import VectorStore, Chunk, SearchResponse, FetchResponse, FetchResult, SearchResult, Document
from uuid import uuid4
import numpy as np
if TYPE_CHECKING:
    from chromadb.base_types import Where, WhereDocument
    from chromadb.api.types import Include

class ChromaVectorStore(VectorStore):
    """ChromaDB implementation of VectorStore."""

    @classmethod
    def class_init(cls, path):
        if not hasattr(cls, "_chroma"):
            #First object initialized so import pinecone and connect to server
            try:
                import chromadb
                if path:
                    cls._chroma = chromadb.PersistentClient(path=path)
                else:
                    cls._chroma = chromadb.EphemeralClient()
            except ImportError:
                raise ImportError("Chroma package is not installed. Please install railtracks[chroma].")
    
    def __init__(
        self,
        collection_name: str,
        embedding_function: Callable[[List[str]], List[List[float]]],
        dimension: int,
        path: Optional[str] = None,
    ):
        self._collection_name = collection_name
        self._embedding_function = embedding_function
        self._dimension = dimension

        ChromaVectorStore.class_init(path)
        self._collection = self._chroma.get_or_create_collection(
            collection_name,
        )
        
    #TODO Fix typing and cross reference
    def upsert(
        self,
        content : List[Chunk] | List[str]
    ) -> List[str]:
        
        if isinstance(content[0], Chunk):
            ids = []
            embeddings = []
            metadatas = []
            documents = []
            for chunk in content:
                id = uuid4().int
                ids.append(str(id))

                embedding = self._embedding_function([chunk.content])[0]
                embeddings.append(embedding)

                metadata = chunk.metadata
                metadata["content"] = chunk.content
                metadatas.append(metadata)

                documents.append(chunk.document)

        elif isinstance(content[0], str):
            ids = []
            embeddings = []
            metadatas = []
            documents = []
            for text in content:
                id = uuid4().int
                ids.append(str(id))

                embedding = self._embedding_function([text])[0]
                embeddings.append(embedding)
                metadata = {"content": text}
                metadatas.append(metadata)

                documents.append(None)

        self._collection.upsert(
            ids=ids,
            embeddings=embeddings,
            metadatas=metadatas,
            documents=documents
            )
        return ids

    #TODO Fix typing and cross reference
    def fetch(
            self, 
            ids: Optional[List[str]]  = None,
            where: Optional[Where] = None,
            limit: Optional[int] = None,
            offset: Optional[int] = None,
            where_document: Optional[WhereDocument] = None,
            ) -> FetchResponse:
        
        results = FetchResponse()
        #currently we ignore Include and assume the left it as default]]
        responses = self._collection.get(
            ids,
            where,
            limit,
            offset,
            where_document,
            include = ["embeddings", "metadatas", "documents"])
        
        for i, response in enumerate(responses["ids"]):
            id = response
            if responses["embeddings"] is not None:
                embedding = responses["embeddings"][i]
            if responses["documents"]:
                document = responses["documents"][i]
            if responses["metadatas"]:
                metadatas = responses["metadatas"][i]

            results.append(FetchResult(
                id=id,
                content=metadatas["content"] if type(metadatas["content"]) is str else "", 
                vector=embedding.tolist(),
                document=document,
                metadata=metadatas))
            
        return results
    
    #There is support for other types of query modalities but for now just list of strings
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
            query_embeddings=[query for query in query_embeddings],
            ids=ids,
            n_results=n_results,
            where=where,
            where_document=where_document,
            include=include
        )
        answer = []
        for i, id_list in enumerate(results["ids"]):
            search_response = SearchResponse()
            for j, id in enumerate(id_list):
                distance = results.get("distances")
                vector = results.get("embeddings")
                document = results.get("documents")
                metadatas = results.get("metadatas")

                if distance is not None:
                    distance = distance[i][j]
                else:
                    raise ValueError("Distance not found in search results.")
                
                if vector is not None:
                    vector = list(vector[i][j])
                else:
                    raise ValueError("Vector not found in search results.")
                
                if document is not None:
                    document = document[i][j]
                else: 
                    raise ValueError("Document not found in search results.")
                
                if metadatas is not None:
                    metadata = metadatas[i][j]
                    content = metadatas[i][j]["content"] #This should always be there since we upserted it but should maybe add check later on
                else:
                    raise ValueError("Metadata not found in search results.")

                search_response.append(SearchResult(
                    id=id,
                    distance=distance,
                    content=content,
                    vector=vector,
                    document=Document(document), #Chroma document is just a str
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