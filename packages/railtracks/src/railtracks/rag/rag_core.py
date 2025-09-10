# rag.py
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Sequence, Union

from railtracks.utils.logging import get_rt_logger

from .chunking_service import TextChunkingService
from .embedding_service import (
    BaseEmbeddingService,
    EmbeddingService,
)
from .text_object import TextObject
from .vector_store import create_store
from .vector_store.base import AbstractVectorStore, SearchResult, VectorRecord

logger = get_rt_logger("rag_core")


@dataclass(frozen=True)
class RAGConfig:
    """
    Unified configuration for RAG.

    - embedding: kwargs forwarded to EmbeddingService(...)
    - store: kwargs forwarded to create_store(...)
    - chunking: kwargs forwarded to TextChunkingService(...)
    - chunk_strategy: override the default chunking strategy if provided
    """

    embedding: Dict = field(default_factory=dict)
    store: Dict = field(default_factory=dict)
    chunking: Dict = field(default_factory=dict)
    chunk_strategy: Optional[Callable[[str], List[str]]] = None


def textobject_to_vectorrecords(text_obj: TextObject) -> List[VectorRecord]:
    """
    Convert a TextObject (with chunks and embeddings already populated) into VectorRecords.

    Uses deterministic ids: {text_obj.hash}-{chunk_index} which are stable and traceable.
    If you need global uniqueness beyond a resource, append a short uuid suffix.
    """
    chunks = text_obj.chunked_content or []
    embeddings = text_obj.embeddings or []
    n = min(len(chunks), len(embeddings))
    vector_records: List[VectorRecord] = []
    base_meta = text_obj.get_metadata()

    for i in range(n):
        metadata = dict(base_meta)
        metadata.update({"chunk_index": i, "chunk": chunks[i]})
        # raise warning if text_obj.hash is empty, generate it on the run
        if not text_obj.hash:
            logger.warning("TextObject has no hash; generating a temporarily Hash")
            text_obj.hash = TextObject.get_resource_hash(text_obj.raw_content)

        record_id = f"{text_obj.hash}-{i}"
        vector_records.append(
            VectorRecord(
                id=record_id,
                vector=embeddings[i],
                text=chunks[i],
                metadata=metadata,
            )
        )
    return vector_records


class RAG:
    """
    RAG (Retrieval-Augmented Generation) system for processing and searching documents.

    You can construct it with:
      1) A single RAGConfig (clean, declarative), and/or
      2) Prebuilt services (embedding_service, vector_store, chunk_service) for advanced control.

    Precedence: explicitly provided services > config-driven creation > defaults.

    Typical use:
        rag = RAG.from_docs(docs, config)
        rag.embed_all()
        results = rag.search("query", top_k=3)
    """

    def __init__(
        self,
        docs: Sequence[str],
        *,
        config: Optional[RAGConfig] = None,
        embedding_service: Optional[BaseEmbeddingService] = None,
        vector_store: Optional[AbstractVectorStore] = None,
        chunk_service: Optional[TextChunkingService] = None,
    ):
        self._config = config or RAGConfig()

        # Build or accept existing services
        self.embed_service = embedding_service or EmbeddingService(
            **self._config.embedding
        )
        self.vector_store = vector_store or create_store(**self._config.store)
        self.chunk_service = chunk_service or TextChunkingService(
            **self._config.chunking,
            strategy=self._config.chunk_strategy or TextChunkingService.chunk_by_token,
        )

        # Initialize TextObjects
        self.text_objects: List[TextObject] = [TextObject(doc) for doc in docs]

    @classmethod
    def from_docs(
        cls,
        docs: Sequence[str],
        config: Optional[RAGConfig] = None,
        **service_overrides,
    ) -> "RAG":
        """
        Convenience constructor. Accepts a config plus optional service overrides:
          - embedding_service
          - vector_store
          - chunk_service
        """
        return cls(docs, config=config, **service_overrides)

    def add_docs(self, docs: Sequence[str]) -> None:
        """Add more raw documents."""
        for doc in docs:
            self.text_objects.append(TextObject(doc))

    def embed_all(self) -> None:
        """
        Chunk and embed all text objects; persist as vector records in the vector store.

        Idempotency note: This method does not deduplicate; calling multiple times will
        append more records for the same docs. Manage deduplication externally if needed.
        """
        for tobj in self.text_objects:
            chunks = self.chunk_service.chunk(tobj.raw_content)
            vectors = self.embed_service.embed(chunks)
            tobj.set_chunked(chunks)
            tobj.set_embeddings(vectors)
            records = textobject_to_vectorrecords(tobj)
            # These are pre-embedded VectorRecord objects
            self.vector_store.add(records)

    def search(self, query: Union[str, List[float]], top_k: int = 3) -> SearchResult:
        """
        Search the vector store for relevant documents.

        If query is text, we embed it; if it's a vector, we pass it through.
        """
        if isinstance(query, str):
            q_vec = self.embed_service.embed([query])[0]
            return self.vector_store.search(q_vec, top_k=top_k)
        else:
            return self.vector_store.search(query, top_k=top_k)
