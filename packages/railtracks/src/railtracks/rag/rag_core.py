# rag.py
import os
import random
from typing import List, Optional

from .chunking_service import TextChunkingService
from .embedding_service import EmbeddingService
from .text_object import TextObject
from .vector_store import create_store
from .vector_store.base import SearchResult, VectorRecord


def textobject_to_vectorrecords(text_obj: TextObject) -> List[VectorRecord]:
    """
    Converts a TextObject instance into a list of VectorRecord instances.
    Each chunk + its embedding becomes a separate VectorRecord.
    """
    # Ensure we have both chunks and embeddings
    chunks = text_obj.chunked_content or []
    embeddings = text_obj.embeddings or []
    n = min(len(chunks), len(embeddings))
    vector_records = []
    base_meta = text_obj.get_metadata()

    for i in range(n):
        metadata = base_meta.copy()
        metadata.update({"chunk_index": i, "chunk": chunks[i]})
        # Use the (resource) hash plus the chunk index for unique id
        random_id = random.randint(1000, 9999)  # Random suffix for uniqueness
        record_id = f"{text_obj.hash}-{random_id}"
        vector_records.append(
            VectorRecord(
                id=record_id, vector=embeddings[i], text=chunks[i], metadata=metadata
            )
        )
    return vector_records


class RAG:
    """RAG (Retrieval-Augmented Generation) system for processing and searching documents.

    This class handles embedding, chunking, and searching of documents.
    """

    def __init__(
        self,
        docs: List[str],  # str
        embed_config: Optional[dict] = None,
        store_config: Optional[dict] = None,
        chunk_config: Optional[dict] = None
    ):
        """Initialize the RAG system.

        Args:
            docs (List[str]): List of documents to process, raw text.
            embed_config (Optional[dict]): Configuration for embedding service.
            store_config (Optional[dict]): Configuration for vector store.
            chunk_config (Optional[dict]): Configuration for chunking service.
        """
        self.text_objects: List[TextObject] = []
        self.embed_service = EmbeddingService(**(embed_config or {}))
        self.vector_store = create_store(**(store_config or {}))
        self.chunk_service = TextChunkingService(
            **(chunk_config or {}),
            strategy=TextChunkingService.chunk_by_token,
        )
        # assert is list of str
        for doc in docs:
            self.text_objects.append(TextObject(doc))

    def embed_all(self):
        """Embed all text objects and store in vector store.

        Required to invoke this before searching.
        """
        chunks_all = []
        for tobj in self.text_objects:
            # chunk returns a list of chunks for each textObject
            chunks = self.chunk_service.chunk(tobj.raw_content)
            vectors = self.embed_service.embed(chunks)
            chunks_all.extend(chunks)
            tobj.set_chunked(chunks)
            tobj.set_embeddings(vectors)
            vobjects = textobject_to_vectorrecords(tobj)
            self.vector_store.add(vobjects)

    def search(self, query: str, top_k: int = 3) -> SearchResult:
        """Search the vector store for relevant documents.

        Args:
            query (str): The search query.
            top_k (int): Number of top results to return.

        Returns:
            List[SearchEntry]: List of search results with text and metadata.
        """
        query_vec = self.embed_service.embed([query])[0]  # Assume one vector only
        return self.vector_store.search(query_vec, top_k=top_k)
