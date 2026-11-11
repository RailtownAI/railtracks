"""Tests for ``RetrievalRuntime.max_consecutive_failures`` (#1781).

``on_error="skip"`` reports a bad document and carries on. A failure that repeats for every
document is not about the documents, so the runtime can stop the run instead of paying for the
rest of the corpus.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator

import pytest
from railtracks.exceptions import ConsecutiveIngestionFailuresError
from railtracks.retrieval import Document, RetrievalRuntime
from railtracks.retrieval.chunking.base import Chunker
from railtracks.retrieval.embedding.base import Embedding
from railtracks.retrieval.embedding.models import EmbeddingMetrics, TextEmbeddings
from railtracks.retrieval.loaders.base import BaseDocumentLoader
from railtracks.retrieval.models import Chunk
from railtracks.retrieval.stores import VectorStore
from railtracks.retrieval.stores.models import StoreEntry
from railtracks.retrieval.stores.vector.backends.in_memory import InMemoryBackend


class _ListLoader(BaseDocumentLoader):
    def __init__(self, docs: list[Document]) -> None:
        self._docs = docs

    async def astream(self) -> AsyncGenerator[Document, None]:
        for doc in self._docs:
            yield doc


class _WordChunker(Chunker):
    """One chunk per word, and a failure for any document holding ``poison``."""

    def chunk(self, document: Document) -> list[Chunk]:
        words = document.content.split()
        if "poison" in words:
            raise RuntimeError("cannot chunk this document")
        return self._make_chunks(document, words)


class _FakeEmbedder(Embedding):
    default_batch_size = 2

    async def aembed(self, texts: list[str]) -> TextEmbeddings:
        return TextEmbeddings(
            vectors=[[float(len(text)), 0.0, 0.0] for text in texts],
            metrics=EmbeddingMetrics(model="fake-model-1", vector_count=len(texts)),
        )


class _BrokenStore(VectorStore):
    """Every write fails, as an unreachable store does."""

    def __init__(self) -> None:
        super().__init__(InMemoryBackend())

    async def write(self, entry: StoreEntry) -> str:
        raise ConnectionError("store unavailable")


def _runtime(
    *,
    store: VectorStore | None = None,
    limit: int | None = 2,
) -> tuple[RetrievalRuntime, VectorStore]:
    store = store or VectorStore(InMemoryBackend())
    runtime = RetrievalRuntime(
        _WordChunker(),
        _FakeEmbedder(),
        store,
        max_consecutive_failures=limit,
    )
    return runtime, store


def _docs(count: int) -> list[Document]:
    return [Document(content=f"word{index} other", source=f"doc{index}.txt") for index in range(count)]


async def test_a_broken_store_stops_the_run_at_the_limit() -> None:
    store = _BrokenStore()
    runtime, _ = _runtime(store=store, limit=3)
    docs = _docs(10)
    yielded = 0

    with pytest.raises(ConsecutiveIngestionFailuresError) as raised:
        async for _event in runtime.ingest(_ListLoader(docs)):
            yielded += 1

    # The first two failures are reported as events; the third ends the run instead.
    assert yielded == 2
    assert raised.value.stage == "store"
    assert raised.value.limit == 3
    assert isinstance(raised.value.last_error, ConnectionError)
    assert raised.value.source == docs[2].source
    # The embedder never saw the rest of the corpus.
    assert await store.count() == 0


async def test_a_success_between_failures_starts_the_count_over() -> None:
    runtime, store = _runtime(limit=2)
    docs = [
        Document(content="poison one", source="bad1.txt"),
        Document(content="alpha beta", source="ok1.txt"),
        Document(content="poison two", source="bad2.txt"),
        Document(content="gamma delta", source="ok2.txt"),
    ]

    stats = await runtime.ingest_all(_ListLoader(docs))

    # Two failures in a row never happen: scattered bad documents are still skipped and reported.
    assert stats.documents_failed == 2
    assert stats.documents_loaded == 4
    assert await store.count() == 4


async def test_the_default_reports_every_failure() -> None:
    store = _BrokenStore()
    runtime, _ = _runtime(store=store, limit=None)

    stats = await runtime.ingest_all(_ListLoader(_docs(5)))

    assert stats.documents_failed == 5


def test_a_non_positive_limit_is_rejected() -> None:
    with pytest.raises(ValueError, match="max_consecutive_failures"):
        RetrievalRuntime(
            _WordChunker(),
            _FakeEmbedder(),
            VectorStore(InMemoryBackend()),
            max_consecutive_failures=0,
        )