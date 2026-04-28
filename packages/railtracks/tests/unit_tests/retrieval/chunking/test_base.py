"""Tests for the Chunker ABC, _make_chunks invariants, and async contract."""

from __future__ import annotations

from collections.abc import AsyncGenerator

import pytest

from railtracks.retrieval import Chunk, Document
from railtracks.retrieval.chunking import Chunker


# -------------------------------------------------------------------
# Test chunker subclass
# -------------------------------------------------------------------


class _PassthroughChunker(Chunker):
    """Trivial subclass whose ``chunk`` just wraps the whole document."""

    def chunk(self, document: Document) -> list[Chunk]:
        return self._make_chunks(document, [document.content])


# -------------------------------------------------------------------
# ABC enforcement
# -------------------------------------------------------------------


def test_chunker_is_abstract():
    with pytest.raises(TypeError):
        Chunker()  # type: ignore[abstract]


# -------------------------------------------------------------------
# _make_chunks invariants
# -------------------------------------------------------------------


def test_make_chunks_propagates_document_id_and_index():
    doc = Document(
        content="abc def", type="text", metadata={"source": "test"}
    )
    chunker = _PassthroughChunker()
    pieces = ["abc ", "def"]
    offsets = [(0, 4), (4, 7)]
    chunks = chunker._make_chunks(doc, pieces, offsets=offsets)

    assert [c.document_id for c in chunks] == [doc.id, doc.id]
    assert [c.index for c in chunks] == [0, 1]
    assert [c.offsets for c in chunks] == offsets
    assert all(c.metadata.get("source") == "test" for c in chunks)


def test_make_chunks_extra_metadata_overrides_inherited_keys():
    doc = Document(
        content="text", type="text", metadata={"category": "base"}
    )
    chunker = _PassthroughChunker()
    chunks = chunker._make_chunks(
        doc,
        ["text"],
        extra_metadata=[{"category": "override", "extra": 1}],
    )
    assert chunks[0].metadata["category"] == "override"
    assert chunks[0].metadata["extra"] == 1


def test_make_chunks_metadata_is_isolated():
    doc = Document(
        content="text", type="text", metadata={"shared": ["a"]}
    )
    chunker = _PassthroughChunker()
    chunks = chunker._make_chunks(doc, ["text"])

    chunks[0].metadata["shared_top_level_key"] = 42
    assert "shared_top_level_key" not in doc.metadata

    # Shallow copy only — nested structures are intentionally not cloned.
    assert chunks[0].metadata["shared"] is doc.metadata["shared"]


def test_make_chunks_rejects_offsets_length_mismatch():
    doc = Document(content="ab", type="text")
    chunker = _PassthroughChunker()
    with pytest.raises(ValueError):
        chunker._make_chunks(doc, ["a", "b"], offsets=[(0, 1)])


def test_make_chunks_rejects_extra_metadata_length_mismatch():
    doc = Document(content="ab", type="text")
    chunker = _PassthroughChunker()
    with pytest.raises(ValueError):
        chunker._make_chunks(doc, ["a", "b"], extra_metadata=[{}])


def test_make_chunks_propagates_parent_chunk_id():
    doc = Document(content="abc", type="text")
    parent = Chunk(content="abc", document_id=doc.id)
    chunker = _PassthroughChunker()
    chunks = chunker._make_chunks(doc, ["a", "bc"], parent_chunk_id=parent.id)
    assert all(c.parent_chunk_id == parent.id for c in chunks)


# -------------------------------------------------------------------
# Sync convenience (chunk / chunk_text)
# -------------------------------------------------------------------


def test_chunk_text_builds_transient_document():
    chunker = _PassthroughChunker()
    chunks = chunker.chunk_text("hello", metadata={"x": 1})
    assert len(chunks) == 1
    assert chunks[0].content == "hello"
    assert chunks[0].metadata == {"x": 1}


def test_chunk_works_sync():
    doc = Document(content="hello", type="text")
    chunker = _PassthroughChunker()
    chunks = chunker.chunk(doc)
    assert len(chunks) == 1
    assert chunks[0].content == "hello"


# -------------------------------------------------------------------
# Async: achunk
# -------------------------------------------------------------------


@pytest.mark.asyncio
async def test_achunk():
    doc = Document(content="hello", type="text")
    chunker = _PassthroughChunker()
    chunks = await chunker.achunk(doc)
    assert len(chunks) == 1
    assert chunks[0].content == "hello"
    assert chunks[0].document_id == doc.id


# -------------------------------------------------------------------
# achunk_text
# -------------------------------------------------------------------


@pytest.mark.asyncio
async def test_achunk_text():
    chunker = _PassthroughChunker()
    chunks = await chunker.achunk_text("world", metadata={"y": 2})
    assert len(chunks) == 1
    assert chunks[0].content == "world"
    assert chunks[0].metadata == {"y": 2}


# -------------------------------------------------------------------
# astream_documents — pipeline composition
# -------------------------------------------------------------------


@pytest.mark.asyncio
async def test_astream_documents():
    docs = [
        Document(content="doc one", type="text"),
        Document(content="doc two", type="text"),
    ]

    async def _doc_stream() -> AsyncGenerator[Document, None]:
        for d in docs:
            yield d

    chunker = _PassthroughChunker()
    chunks = [c async for c in chunker.astream_documents(_doc_stream())]

    assert len(chunks) == 2
    assert chunks[0].content == "doc one"
    assert chunks[1].content == "doc two"
    assert chunks[0].document_id == docs[0].id
    assert chunks[1].document_id == docs[1].id


@pytest.mark.asyncio
async def test_astream_documents_empty_stream():
    async def _empty() -> AsyncGenerator[Document, None]:
        return
        yield  # noqa: unreachable — makes this a valid async generator

    chunker = _PassthroughChunker()
    chunks = [c async for c in chunker.astream_documents(_empty())]
    assert chunks == []
