from __future__ import annotations

import hashlib
from collections.abc import AsyncGenerator
from dataclasses import dataclass, field
from typing import Any, Callable
from uuid import UUID

from railtracks.utils.logging.create import get_rt_logger

from .chunking.base import Chunker
from .chunking.tokenization import Tokenizer
from .embedding.base import Embedding
from .embedding.models import EmbeddingFailure, EmbeddingMetrics, EmbeddingResult
from .errors import EmbeddingModelMismatchError
from .loaders.base import BaseDocumentLoader
from .models import Chunk, Document, EmbeddedChunk, RetrievalResult, RetrievedChunk
from .stores.models import StoreEntry, StoreQuery, StoreScope
from .stores.protocol import Store

logger = get_rt_logger(__name__)


@dataclass
class BatchIngested:
    """A batch of chunks that finished embedding and was written to the store.

    ``batch_index`` is **per-document**: it starts at 0 for each document and
    counts that document's batches (both successful and failed) in order. It
    is not a run-global counter — to track overall progress, count events or
    read ``IngestionStats``.

    ``metrics`` carries the per-batch usage and timing reported by the
    embedder (tokens, dollar cost, latency, vector count). Use it to track
    per-ingest cost without having to wrap the embedder.
    """

    document_id: UUID
    embedded_chunks: list[EmbeddedChunk]
    batch_index: int
    metrics: EmbeddingMetrics | None = None


@dataclass
class DocumentFailed:
    """A document that had at least one failed embedding batch.

    Note: successful batches for the same document *are* written to the
    store. ``DocumentFailed`` is an informational signal that the document
    is now partial — callers may want to retry, delete, or accept the
    partial state.
    """

    document_id: UUID
    source: str | None
    errors: list[Exception]


@dataclass
class DocumentSkipped:
    """A document skipped during ingest because the store already has an
    entry with the same ``source_path`` and ``content_hash``."""

    document_id: UUID
    source: str | None
    reason: str = "unchanged"


@dataclass
class IngestionStats:
    """Summary of a complete ingest run.

    ``total_metrics`` accumulates per-batch ``EmbeddingMetrics`` (tokens,
    dollar cost, latency, vector count) across every successful batch in
    the run, so callers can read a single total for billing/observability.
    """

    documents_loaded: int = 0
    documents_failed: int = 0
    documents_skipped: int = 0
    chunks_created: int = 0
    chunks_embedded: int = 0
    batches_failed: int = 0
    batch_failures: list[EmbeddingFailure] = field(default_factory=list)
    failed_documents: list[DocumentFailed] = field(default_factory=list)
    total_metrics: EmbeddingMetrics = field(default_factory=EmbeddingMetrics)


def _content_hash(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def _entry_to_chunk(entry: StoreEntry) -> Chunk:
    return Chunk(
        id=entry.chunk_id,
        content=entry.content,
        document_id=entry.document_id,
        index=entry.chunk_index,
        parent_chunk_id=entry.parent_chunk_id,
        offsets=entry.chunk_offsets,
        metadata=entry.chunk_metadata,
    )


class RetrievalRuntime:
    """Orchestrates loading, chunking, embedding, storage, and retrieval.

    The runtime captures *how* to process documents (chunker + embedder +
    store + scope); the loader passed to :meth:`ingest` decides *what* to
    process. A single runtime can ingest from multiple sources, mix
    chunking strategies via separate runtimes against the same store,
    and update existing documents by re-ingesting them.

    Args:
        chunker: Splits documents into chunks.
        embedder: Embeds chunk text into vectors.
        store: Receives written ``StoreEntry``s and serves similarity search.
        batch_size: Items per embedding batch. Falls back to
            ``embedder.default_batch_size`` when omitted; raises
            ``ValueError`` at construction if neither is set.
        scope: Applied to every entry written and to every read query.
            Single-tenant callers can leave this ``None``.
        on_ingest: Synchronous callback invoked with each ``IngestionEvent``
            as it is yielded. Wrap in ``asyncio.create_task`` for async logging.
        on_retrieve: Synchronous callback invoked with the query string and
            the ``RetrievalResult`` after each retrieve call.
        max_tokens: When set, chunks whose token count exceeds this limit
            are dropped before embedding and reported via
            ``EmbeddingFailure`` rather than being sent to the provider.
            Requires ``tokenizer`` (defaults to ``TiktokenTokenizer``).
        tokenizer: Tokenizer used to enforce ``max_tokens``. Defaults to
            ``TiktokenTokenizer`` lazily when ``max_tokens`` is set.
    """

    def __init__(
        self,
        chunker: Chunker,
        embedder: Embedding,
        store: Store,
        *,
        batch_size: int | None = None,
        scope: StoreScope | None = None,
        on_ingest: Callable[
            [BatchIngested | EmbeddingFailure | DocumentFailed | DocumentSkipped], None
        ]
        | None = None,
        on_retrieve: Callable[[str, RetrievalResult], None] | None = None,
        max_tokens: int | None = None,
        tokenizer: Tokenizer | None = None,
    ) -> None:
        self._chunker = chunker
        self._embedder = embedder
        self._store = store
        self._scope = scope
        self._batch_size = self._resolve_batch_size(batch_size, embedder)
        self._on_ingest = on_ingest
        self._on_retrieve = on_retrieve
        self._max_tokens = max_tokens
        if max_tokens is not None and tokenizer is None:
            from .chunking.tokenization import TiktokenTokenizer

            tokenizer = TiktokenTokenizer()
        self._tokenizer = tokenizer
        # Captured on the first successful embedded batch and checked at
        # retrieve time; in-process only.
        self._captured_model: str | None = None

    @property
    def store(self) -> Store:
        return self._store

    @property
    def embedder(self) -> Embedding:
        return self._embedder

    @property
    def chunker(self) -> Chunker:
        return self._chunker

    @property
    def scope(self) -> StoreScope | None:
        return self._scope

    @property
    def batch_size(self) -> int:
        return self._batch_size

    @property
    def max_tokens(self) -> int | None:
        return self._max_tokens

    @staticmethod
    def _resolve_batch_size(batch_size: int | None, embedder: Embedding) -> int:
        bs = batch_size if batch_size is not None else embedder.default_batch_size
        if bs is None:
            raise ValueError(
                f"{type(embedder).__name__} does not declare a "
                "default_batch_size. Pass batch_size= to RetrievalRuntime "
                "or set default_batch_size on the embedder class."
            )
        return bs

    async def ingest(
        self, loader: BaseDocumentLoader
    ) -> AsyncGenerator[
        BatchIngested | EmbeddingFailure | DocumentFailed | DocumentSkipped, None
    ]:
        """Stream loader → chunker → embedder → store, yielding per-batch events.

        Yields:
            ``BatchIngested`` after each successful batch finishes writing,
            ``EmbeddingFailure`` for any failed batch, and ``DocumentFailed``
            once at end-of-document for each document that had any failed
            batch. Successful batches for a partially-failed document are
            still written; ``DocumentFailed`` signals the partial state.
        """
        stats = IngestionStats()
        async for event in self._ingest_with_stats(loader, stats):
            if self._on_ingest is not None:
                self._on_ingest(event)
            yield event

    async def ingest_all(self, loader: BaseDocumentLoader) -> IngestionStats:
        """Drain `ingest` and return aggregate counts."""
        stats = IngestionStats()
        async for event in self._ingest_with_stats(loader, stats):
            if self._on_ingest is not None:
                self._on_ingest(event)
        return stats

    async def _ingest_with_stats(
        self,
        loader: BaseDocumentLoader,
        stats: IngestionStats,
    ) -> AsyncGenerator[
        BatchIngested | EmbeddingFailure | DocumentFailed | DocumentSkipped, None
    ]:
        async for doc in loader.astream():
            async for event in self._ingest_document(doc, stats):
                yield event

    async def _ingest_document(
        self, doc: Document, stats: IngestionStats
    ) -> AsyncGenerator[
        BatchIngested | EmbeddingFailure | DocumentFailed | DocumentSkipped, None
    ]:
        stats.documents_loaded += 1
        doc.content_hash = _content_hash(doc.content)

        if await self._is_complete_duplicate(doc):
            stats.documents_skipped += 1
            yield DocumentSkipped(document_id=doc.id, source=doc.source)
            return

        chunks = await self._chunker.achunk(doc)
        stats.chunks_created += len(chunks)
        if not chunks:
            return

        self._stamp_staleness_metadata(doc, chunks)

        # Token-size guard: drop oversized chunks before embedding to avoid
        # provider 4xx errors. Each oversize chunk surfaces as an
        # EmbeddingFailure carried into the document's accumulated errors.
        doc_errors: list[Exception] = []
        chunks, failures = self._split_oversized(chunks, stats)
        for failure in failures:
            doc_errors.extend(failure.errors)
            yield failure
        if not chunks:
            if doc_errors:
                yield self._record_document_failed(doc, doc_errors, stats)
            return

        # Stamp the final (post-token-guard) chunk count onto every chunk so a
        # later staleness check can tell a complete document from a
        # partially-written one. Every chunk carries the same total, so reading
        # any one persisted chunk reveals how many were expected.
        for chunk in chunks:
            chunk.metadata["doc_chunk_count"] = len(chunks)

        async for event in self._embed_and_store(doc, chunks, stats, doc_errors):
            yield event

        if doc_errors:
            yield self._record_document_failed(doc, doc_errors, stats)

    async def _is_complete_duplicate(self, doc: Document) -> bool:
        """Whether the store already holds a *complete* copy of ``doc``.

        Skip re-embedding only when as many chunks are present as the last
        write expected. A partially-written document (some chunks present after
        an interrupted ingest) has fewer than expected and is re-ingested rather
        than left broken. find() is metadata-only (no vector search); the second
        call caps its work at the document's own chunk count, and only runs when
        a prior version exists. (Counting is done via find() rather than a
        count() call so the runtime depends only on the Store protocol.)
        """
        if doc.source is None:
            return False
        stale_filters = {
            "source_path": doc.source,
            "content_hash": doc.content_hash,
        }
        existing = await self._store.find(stale_filters, limit=1)
        if not existing:
            return False
        expected = existing[0].chunk_metadata.get("doc_chunk_count")
        if expected is None:
            # Legacy entry written before count-aware staleness:
            # preserve the original "exists => complete" behavior.
            return True
        present = await self._store.find(stale_filters, limit=expected)
        return len(present) >= expected

    @staticmethod
    def _stamp_staleness_metadata(doc: Document, chunks: list[Chunk]) -> None:
        """Inject staleness-detection metadata into every chunk so future
        `find` calls can identify whether this document has changed."""
        for chunk in chunks:
            if doc.source is not None:
                chunk.metadata.setdefault("source_path", doc.source)
            if doc.content_hash is not None:
                chunk.metadata.setdefault("content_hash", doc.content_hash)

    def _split_oversized(
        self, chunks: list[Chunk], stats: IngestionStats
    ) -> tuple[list[Chunk], list[EmbeddingFailure]]:
        """Partition chunks into embeddable ones and per-chunk failures.

        Returns ``(ok_chunks, failures)``; each oversize chunk becomes a
        single-chunk ``EmbeddingFailure`` and is recorded in ``stats``.
        """
        if self._max_tokens is None or self._tokenizer is None:
            return chunks, []
        ok_chunks: list[Chunk] = []
        failures: list[EmbeddingFailure] = []
        for chunk in chunks:
            tokens = self._tokenizer.count(chunk.content)
            if tokens > self._max_tokens:
                err = ValueError(
                    f"chunk {chunk.id} has {tokens} tokens "
                    f"(>{self._max_tokens}); dropped before embedding"
                )
                stats.batches_failed += 1
                failure = EmbeddingFailure(chunks=[chunk], errors=[err])
                stats.batch_failures.append(failure)
                failures.append(failure)
            else:
                ok_chunks.append(chunk)
        return ok_chunks, failures

    async def _embed_and_store(
        self,
        doc: Document,
        chunks: list[Chunk],
        stats: IngestionStats,
        doc_errors: list[Exception],
    ) -> AsyncGenerator[
        BatchIngested | EmbeddingFailure | DocumentFailed | DocumentSkipped, None
    ]:
        # batch_index is per-document: it counts batches (successful and
        # failed) within this document and resets for the next one.
        batch_index = 0
        delete_done = False
        async for batch in self._embedder.astream_batches(
            chunks, batch_size=self._batch_size
        ):
            if isinstance(batch, EmbeddingResult):
                if not delete_done:
                    await self._store.delete_where({"document_id": str(doc.id)})
                    delete_done = True
                for embedded in batch.chunks:
                    self._capture_model(embedded)
                    entry = StoreEntry.from_chunk(embedded, scope=self._scope)
                    await self._store.write(entry)
                stats.chunks_embedded += len(batch.chunks)
                stats.total_metrics = stats.total_metrics + batch.metrics
                yield BatchIngested(
                    document_id=doc.id,
                    embedded_chunks=batch.chunks,
                    batch_index=batch_index,
                    metrics=batch.metrics,
                )
            else:
                doc_errors.extend(batch.errors)
                stats.batches_failed += 1
                stats.batch_failures.append(batch)
                yield batch
            batch_index += 1

    def _capture_model(self, embedded: EmbeddedChunk) -> None:
        """Record the embedding model from the first successful chunk so later
        retrieve() calls can enforce model consistency."""
        if self._captured_model is None and embedded.embedding_model:
            self._captured_model = embedded.embedding_model
            logger.info(
                "RetrievalRuntime captured embedding model %r "
                "from first successful batch; subsequent retrieve() "
                "calls will enforce this model.",
                self._captured_model,
            )

    @staticmethod
    def _record_document_failed(
        doc: Document, doc_errors: list[Exception], stats: IngestionStats
    ) -> DocumentFailed:
        failed = DocumentFailed(
            document_id=doc.id,
            source=doc.source,
            errors=doc_errors,
        )
        stats.documents_failed += 1
        stats.failed_documents.append(failed)
        return failed

    async def delete_document(self, document_id: UUID) -> None:
        """Remove all chunks for a document from the store.

        Convenience wrapper around ``store.delete_where({"document_id": ...})``
        so callers don't need to know the metadata key.
        """
        await self._store.delete_where({"document_id": str(document_id)})

    async def retrieve(
        self,
        query: str,
        top_k: int = 5,
        metadata_filters: dict[str, Any] | None = None,
        scope: StoreScope | None = None,
    ) -> RetrievalResult:
        """Embed ``query`` and return the top ``top_k`` matches from the store.

        Args:
            query: The text to embed and search with.
            top_k: Maximum number of results.
            metadata_filters: Additional equality filters on chunk metadata.
            scope: Overrides the runtime's default scope for this call.

        Raises:
            EmbeddingModelMismatchError: When the embedder reports a model
                different from the one captured on first ingest.
        """
        text_result = await self._embedder.aembed([query])
        embed_model = text_result.metrics.model
        if (
            self._captured_model is not None
            and embed_model
            and embed_model != self._captured_model
        ):
            raise EmbeddingModelMismatchError(
                f"Embedder produced vectors with model {embed_model!r} but "
                f"store was built with {self._captured_model!r}. Similarity "
                "scores across models are meaningless; rebuild the store "
                "with the correct embedder or switch embedders."
            )

        store_query = StoreQuery(
            text=query,
            scope=scope if scope is not None else self._scope,
            embedding=text_result.vectors[0],
            top_k=top_k,
            metadata_filters=metadata_filters,
        )
        store_hits = await self._store.read(store_query)
        chunks = [
            RetrievedChunk(
                chunk=_entry_to_chunk(hit.entry),
                score=hit.score,
                rank=hit.rank,
                source_retriever=hit.source_retriever,
                rerank_score=hit.rerank_score,
            )
            for hit in store_hits
        ]
        result = RetrievalResult(query=query, chunks=chunks)
        if self._on_retrieve is not None:
            self._on_retrieve(query, result)
        return result
