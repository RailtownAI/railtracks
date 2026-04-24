"""Cross-chunker compatibility: all chunkers conform to the Chunker ABC.

The retrieval pipeline only cares about the ``Chunker`` interface, so we
exercise every concrete chunker through it and assert the baseline
invariants hold uniformly.
"""

from __future__ import annotations

import pytest

from railtracks.retrieval.chunking import (
    Chunker,
    FixedTokenChunker,
    MarkdownHeaderChunker,
    RecursiveCharacterChunker,
    SentenceChunker,
)

ALL_CHUNKERS = [
    lambda: FixedTokenChunker(chunk_size=50, overlap=10),
    lambda: RecursiveCharacterChunker(chunk_size=80, overlap=20),
    lambda: SentenceChunker(chunk_size=2, overlap=0),
    lambda: MarkdownHeaderChunker(),
]


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
