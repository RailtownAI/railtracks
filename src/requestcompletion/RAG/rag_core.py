# rag.py
import os
import random
from typing import Any, List, Optional

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
    def __init__(
        self,
        docs: List[Any],  # str, file path, or raw content
        embed_config: Optional[dict] = None,
        store_config: Optional[dict] = None,
        chunk_config: Optional[dict] = None,
        input_type: str = "text",  # 'text' or 'path'
    ):
        self.text_objects: List[TextObject] = []
        self.embed_service = EmbeddingService(**(embed_config or {}))
        self.vector_store = create_store(**(store_config or {}))
        self.chunk_service = TextChunkingService(
            **(chunk_config or {}),
            strategy=TextChunkingService.chunk_by_token,
        )
        if input_type.lower() == "text":
            for doc in docs:
                self.text_objects.append(TextObject(doc))
        elif input_type.lower() == "path":
            # create TextObjects for file paths
            for doc in docs:
                if os.path.exists(doc):
                    with open(doc, "r", encoding="utf-8") as f:
                        content = f.read()
                    self.text_objects.append(TextObject(raw_content=content, path=doc))
                else:
                    raise ValueError(f"File path {doc} does not exist.")
        else:
            raise ValueError(
                f"input_type must be 'text' or 'path', instead got '{input_type}'."
            )

    def embed_all(self):
        chunks_all = []
        for tobj in self.text_objects:
            # chunk return a list of chunks for each textObject
            chunks = self.chunk_service.chunk(tobj.raw_content)
            vectors = self.embed_service.embed(chunks)
            chunks_all.extend(chunks)
            tobj.set_chunked(chunks)
            tobj.set_embeddings(vectors)
            vobjects = textobject_to_vectorrecords(tobj)
            self.vector_store.add(vobjects)

    def search(self, query: str, top_k=3) -> List[SearchResult]:
        query_vec = self.embed_service.embed([query])[0]  # Assume one vector only
        return self.vector_store.search(query_vec, top_k=top_k)
