"""Tests for the Chunker ABC and _make_chunks invariants."""

from __future__ import annotations

import pytest

from railtracks.retrieval import Chunk, Document
from railtracks.retrieval.chunking import Chunker


class _PassthroughChunker(Chunker):
    """Trivial subclass whose ``chunk`` just wraps the whole document."""

    def chunk(self, document: Document) -> list[Chunk]:
        return self._make_chunks(document, [document.content])


def test_chunker_is_abstract():
    with pytest.raises(TypeError):
        Chunker()  # type: ignore[abstract]


def test_make_chunks_propagates_document_id_and_index():
    doc = Document(
        content="abc def", type="text/plain", metadata={"source": "test"}
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
        content="text", type="text/plain", metadata={"category": "base"}
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
        content="text", type="text/plain", metadata={"shared": ["a"]}
    )
    chunker = _PassthroughChunker()
    chunks = chunker._make_chunks(doc, ["text"])

    chunks[0].metadata["shared_top_level_key"] = 42
    assert "shared_top_level_key" not in doc.metadata

    # Shallow copy only — nested structures are intentionally not cloned.
    # The invariant we enforce is at the top-level dict, matching the
    # design doc ("shallow-copied metadata inheritance").
    assert chunks[0].metadata["shared"] is doc.metadata["shared"]


def test_make_chunks_rejects_offsets_length_mismatch():
    doc = Document(content="ab", type="text/plain")
    chunker = _PassthroughChunker()
    with pytest.raises(ValueError):
        chunker._make_chunks(doc, ["a", "b"], offsets=[(0, 1)])


def test_make_chunks_rejects_extra_metadata_length_mismatch():
    doc = Document(content="ab", type="text/plain")
    chunker = _PassthroughChunker()
    with pytest.raises(ValueError):
        chunker._make_chunks(doc, ["a", "b"], extra_metadata=[{}])


def test_make_chunks_propagates_parent_chunk_id():
    doc = Document(content="abc", type="text/plain")
    parent = Chunk(content="abc", document_id=doc.id)
    chunker = _PassthroughChunker()
    chunks = chunker._make_chunks(doc, ["a", "bc"], parent_chunk_id=parent.id)
    assert all(c.parent_chunk_id == parent.id for c in chunks)


def test_chunk_text_builds_transient_document():
    chunker = _PassthroughChunker()
    chunks = chunker.chunk_text("hello", metadata={"x": 1})
    assert len(chunks) == 1
    assert chunks[0].content == "hello"
    assert chunks[0].metadata == {"x": 1}
