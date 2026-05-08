"""High-level orchestration of the retrieval pipeline.

:class:`RetrievalRuntime` wires together a chunker, embedder, and
:class:`VectorStore` into the full ingest/retrieve flow. Loaders are passed
into ``ingest()`` rather than constructor-time so a single runtime can
ingest from multiple sources or update existing documents.
"""

from __future__ import annotations

import hashlib
from collections.abc import AsyncGenerator
from dataclasses import dataclass, field
from typing import Union
from uuid import UUID

from railtracks.vector_stores.filter import BaseExpr

from .chunking.base import Chunker
from .embedding.base import Embedding
from .embedding.models import EmbeddingFailure, EmbeddingResult
from .loaders.base import BaseDocumentLoader
from .models import EmbeddedChunk, RetrievalResult
from .storage.base import VectorStore


class EmbeddingModelMismatchError(RuntimeError):
    """Raised when the runtime's embedder model differs from the store's.

    Mixing vectors from different embedding models silently produces
    meaningless similarity scores, so the runtime fails loudly before
    issuing the search.
    """


@dataclass
class BatchIngested:
    """A batch of chunks that finished embedding for a document."""

    document_id: UUID
    embedded_chunks: list[EmbeddedChunk]
    batch_index: int


@dataclass
class DocumentFailed:
    """A document that had at least one failed embedding batch.

    Emitted once per document at end-of-document when any of its batches
    failed. The document is not written to the store; callers can use
    ``source`` (when available) to drive a targeted retry without
    re-iterating the entire loader.
    """

    document_id: UUID
    source: str | None
    errors: list[Exception]


IngestionEvent = Union[BatchIngested, EmbeddingFailure, DocumentFailed]


@dataclass
class IngestionStats:
    """Summary of a complete ingest run."""

    documents_loaded: int = 0
    documents_failed: int = 0
    chunks_created: int = 0
    chunks_embedded: int = 0
    batches_failed: int = 0
    batch_failures: list[EmbeddingFailure] = field(default_factory=list)
    failed_documents: list[DocumentFailed] = field(default_factory=list)


def _content_hash(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


class RetrievalRuntime:
    """Orchestrates loading, chunking, embedding, storage, and retrieval.

    The runtime captures *how* to process documents (chunker + embedder +
    store); the loader passed to :meth:`ingest` decides *what* to
    process. This split lets a single runtime ingest from multiple
    sources, mix chunking strategies via separate runtimes against the
    same store, and update existing documents by re-ingesting them.

    Args:
        chunker: Splits documents into chunks.
        embedder: Embeds chunk text into vectors.
        store: Receives embedded chunks and serves similarity search.
        batch_size: Items per embedding batch. Falls back to
            ``embedder.default_batch_size`` when omitted; raises at
            ingest time if neither is set.
    """

    def __init__(
        self,
        chunker: Chunker,
        embedder: Embedding,
        store: VectorStore,
        *,
        batch_size: int | None = None,
    ) -> None:
        self._chunker = chunker
        self._embedder = embedder
        self._store = store
        self._batch_size = batch_size

    def _resolve_batch_size(self) -> int:
        bs = (
            self._batch_size
            if self._batch_size is not None
            else self._embedder.default_batch_size
        )
        if bs is None:
            raise ValueError(
                f"{type(self._embedder).__name__} does not declare a "
                "default_batch_size. Pass batch_size= to RetrievalRuntime "
                "or set default_batch_size on the embedder class."
            )
        return bs

    async def ingest(
        self, loader: BaseDocumentLoader
    ) -> AsyncGenerator[IngestionEvent, None]:
        """Stream loader → chunker → embedder → store, yielding per-batch events.

        Yields:
            ``BatchIngested`` per successfully embedded batch,
            ``EmbeddingFailure`` per failed batch, and ``DocumentFailed``
            once at end-of-document for each document that had any failed
            batch. A document with any failed batch is *not* written to
            the store, so partial documents never appear in search
            results; ``DocumentFailed.source`` lets callers drive a
            targeted retry.
        """
        stats = IngestionStats()
        async for event in self._ingest_with_stats(loader, stats):
            yield event

    async def ingest_all(self, loader: BaseDocumentLoader) -> IngestionStats:
        """Drain :meth:`ingest` and return aggregate counts."""
        stats = IngestionStats()
        async for _ in self._ingest_with_stats(loader, stats):
            pass
        return stats

    async def _ingest_with_stats(
        self,
        loader: BaseDocumentLoader,
        stats: IngestionStats,
    ) -> AsyncGenerator[IngestionEvent, None]:
        bs = self._resolve_batch_size()
        batch_index = 0
        async for doc in loader.astream():
            stats.documents_loaded += 1
            doc.content_hash = _content_hash(doc.content)
            chunks = await self._chunker.achunk(doc)
            stats.chunks_created += len(chunks)
            if not chunks:
                continue

            embedded_for_doc: list[EmbeddedChunk] = []
            doc_errors: list[Exception] = []
            async for batch in self._embedder.astream_batches(
                chunks, batch_size=bs
            ):
                if isinstance(batch, EmbeddingResult):
                    embedded_for_doc.extend(batch.chunks)
                    stats.chunks_embedded += len(batch.chunks)
                    yield BatchIngested(
                        document_id=doc.id,
                        embedded_chunks=batch.chunks,
                        batch_index=batch_index,
                    )
                else:
                    doc_errors.extend(batch.errors)
                    stats.batches_failed += 1
                    stats.batch_failures.append(batch)
                    yield batch
                batch_index += 1

            if doc_errors:
                failed = DocumentFailed(
                    document_id=doc.id,
                    source=doc.source,
                    errors=doc_errors,
                )
                stats.documents_failed += 1
                stats.failed_documents.append(failed)
                yield failed
            elif embedded_for_doc:
                await self._store.add_document(doc.id, embedded_for_doc)

    async def retrieve(
        self,
        query: str,
        top_k: int = 5,
        where: BaseExpr | None = None,
    ) -> RetrievalResult:
        """Embed ``query`` and return the top ``top_k`` matches from the store.

        Raises:
            EmbeddingModelMismatchError: When the embedder reports a
                different model than the store was built with.
        """
        text_result = await self._embedder.aembed([query])
        embed_model = text_result.metrics.model
        store_model = self._store.embedding_model
        if embed_model and embed_model != store_model:
            raise EmbeddingModelMismatchError(
                f"Embedder produced vectors with model {embed_model!r} but "
                f"store was built with {store_model!r}. Similarity scores "
                "across models are meaningless; rebuild the store with the "
                "correct embedder or switch embedders."
            )
        chunks = await self._store.search(
            text_result.vectors[0], top_k=top_k, where=where
        )
        return RetrievalResult(query=query, chunks=chunks)
