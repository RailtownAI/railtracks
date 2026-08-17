"""Cross-chunker compatibility: all chunkers conform to the Chunker ABC.

The retrieval pipeline only cares about the ``Chunker`` interface, so we
exercise every concrete chunker through it and assert the baseline
invariants hold uniformly — both sync and async.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator

import pytest
from railtracks.retrieval import Document
from railtracks.retrieval.chunking import (
    Chunker,
    FixedTokenChunker,
    IdentityChunker,
    MarkdownHeaderChunker,
    RecursiveCharacterChunker,
    SemanticChunker,
    SentenceChunker,
)
from railtracks.retrieval.embedding import Embedding, EmbeddingMetrics, TextEmbeddings


class _FakeEmbedder(Embedding):
    default_batch_size = 8

    def embed(self, texts: list[str]) -> TextEmbeddings:
        return TextEmbeddings(
            vectors=[[float(len(t))] for t in texts],
            metrics=EmbeddingMetrics(vector_count=len(texts)),
        )

    async def aembed(self, texts: list[str]) -> TextEmbeddings:
        return self.embed(texts)


ALL_CHUNKERS = [
    lambda: FixedTokenChunker(chunk_size=50, overlap=10),
    lambda: IdentityChunker(),
    lambda: RecursiveCharacterChunker(chunk_size=80, overlap=20),
    lambda: SentenceChunker(chunk_size=2, overlap=0),
    lambda: MarkdownHeaderChunker(),
    lambda: SemanticChunker(embedder=_FakeEmbedder()),
]


# -------------------------------------------------------------------
# Sync interface
# -------------------------------------------------------------------


@pytest.mark.parametrize("factory", ALL_CHUNKERS)
def test_all_chunkers_subclass_chunker_abc(factory):
    assert isinstance(factory(), Chunker)


@pytest.mark.parametrize("factory", ALL_CHUNKERS)
def test_all_chunkers_empty_document(factory, empty_doc):
    assert factory().chunk(empty_doc) == []


@pytest.mark.parametrize("factory", ALL_CHUNKERS)
def test_all_chunkers_propagate_document_id(factory, multi_paragraph_doc):
    chunks = factory().chunk(multi_paragraph_doc)
    assert chunks  # non-empty for this fixture
    assert all(c.document_id == multi_paragraph_doc.id for c in chunks)


@pytest.mark.parametrize("factory", ALL_CHUNKERS)
def test_all_chunkers_dense_indices(factory, multi_paragraph_doc):
    chunks = factory().chunk(multi_paragraph_doc)
    assert [c.index for c in chunks] == list(range(len(chunks)))


@pytest.mark.parametrize("factory", ALL_CHUNKERS)
def test_all_chunkers_invokable_via_chunk_text(factory):
    chunks = factory().chunk_text("Alpha. Beta. Gamma. Delta. " * 5)
    assert all(c.content for c in chunks)


# -------------------------------------------------------------------
# Async interface — achunk parity
# -------------------------------------------------------------------


@pytest.mark.parametrize("factory", ALL_CHUNKERS)
@pytest.mark.asyncio
async def test_all_chunkers_achunk_matches_chunk(factory, multi_paragraph_doc):
    chunker = factory()
    sync_chunks = chunker.chunk(multi_paragraph_doc)
    async_chunks = await chunker.achunk(multi_paragraph_doc)

    assert len(async_chunks) == len(sync_chunks)
    for sc, ac in zip(sync_chunks, async_chunks):
        assert sc.content == ac.content
        assert sc.document_id == ac.document_id
        assert sc.index == ac.index
        assert sc.offsets == ac.offsets


@pytest.mark.parametrize("factory", ALL_CHUNKERS)
@pytest.mark.asyncio
async def test_all_chunkers_achunk_empty_document(factory, empty_doc):
    assert await factory().achunk(empty_doc) == []


@pytest.mark.parametrize("factory", ALL_CHUNKERS)
@pytest.mark.asyncio
async def test_all_chunkers_achunk_text(factory):
    chunks = await factory().achunk_text("Alpha. Beta. Gamma. Delta. " * 5)
    assert all(c.content for c in chunks)


# -------------------------------------------------------------------
# Async interface — astream_documents pipeline
# -------------------------------------------------------------------


@pytest.mark.parametrize("factory", ALL_CHUNKERS)
@pytest.mark.asyncio
async def test_all_chunkers_astream_documents(factory, multi_paragraph_doc):
    docs = [multi_paragraph_doc]

    async def _doc_stream() -> AsyncGenerator[Document, None]:
        for d in docs:
            yield d

    chunker = factory()
    streamed = [c async for c in chunker.astream_documents(_doc_stream())]
    direct = chunker.chunk(multi_paragraph_doc)

    assert len(streamed) == len(direct)
    for s, d in zip(streamed, direct):
        assert s.content == d.content
        assert s.document_id == d.document_id


# -------------------------------------------------------------------
# Async interface — concurrency
# -------------------------------------------------------------------


@pytest.mark.asyncio
async def test_all_chunkers_concurrent_achunk(multi_paragraph_doc):
    chunkers = [f() for f in ALL_CHUNKERS]
    results = await asyncio.gather(
        *[c.achunk(multi_paragraph_doc) for c in chunkers]
    )
    assert len(results) == len(ALL_CHUNKERS)
    for chunks in results:
        assert len(chunks) >= 1
        assert all(c.document_id == multi_paragraph_doc.id for c in chunks)
