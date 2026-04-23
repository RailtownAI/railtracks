"""Tests for RecursiveCharacterChunker + RecursiveSplitter."""

from __future__ import annotations

import pytest

from railtracks.retrieval import Document
from railtracks.retrieval.chunking import (
    RecursiveCharacterChunker,
    RecursiveSplitter,
    Splitter,
)


def test_checklist(chunker_checklist, multi_paragraph_doc, short_doc, empty_doc):
    chunker_checklist(
        lambda: RecursiveCharacterChunker(chunk_size=80, overlap=20),
        multi_paragraph_doc,
        short_doc,
        empty_doc,
    )


def test_offsets_slice_back_to_content(multi_paragraph_doc):
    chunker = RecursiveCharacterChunker(chunk_size=80, overlap=20)
    chunks = chunker.chunk(multi_paragraph_doc)
    for c in chunks:
        assert c.offsets is not None
        s, e = c.offsets
        assert multi_paragraph_doc.content[s:e] == c.content


def test_chunks_cover_the_document(multi_paragraph_doc):
    chunker = RecursiveCharacterChunker(chunk_size=80, overlap=20)
    chunks = chunker.chunk(multi_paragraph_doc)
    covered = [False] * len(multi_paragraph_doc.content)
    for c in chunks:
        s, e = c.offsets
        for i in range(s, e):
            covered[i] = True
    assert all(covered)


def test_overlap_produces_shared_content_between_adjacent_chunks():
    text = "\n\n".join(f"paragraph {i} " + "word " * 30 for i in range(5))
    doc = Document(content=text, type="text/plain")
    chunker = RecursiveCharacterChunker(chunk_size=150, overlap=50)
    chunks = chunker.chunk(doc)
    assert len(chunks) >= 2
    for a, b in zip(chunks, chunks[1:]):
        assert b.offsets[0] < a.offsets[1], (
            "adjacent chunks should share some character range when overlap > 0"
        )


def test_zero_overlap_chunks_are_disjoint():
    text = "\n\n".join(f"paragraph {i}. " + "word " * 40 for i in range(6))
    doc = Document(content=text, type="text/plain")
    chunker = RecursiveCharacterChunker(chunk_size=180, overlap=0)
    chunks = chunker.chunk(doc)
    for a, b in zip(chunks, chunks[1:]):
        assert a.offsets[1] <= b.offsets[0]


def test_rejects_invalid_construction():
    with pytest.raises(ValueError):
        RecursiveCharacterChunker(chunk_size=0)
    with pytest.raises(ValueError):
        RecursiveCharacterChunker(chunk_size=100, overlap=-1)
    with pytest.raises(ValueError):
        RecursiveCharacterChunker(chunk_size=100, overlap=100)


def test_recursive_splitter_satisfies_splitter_protocol():
    splitter = RecursiveSplitter(chunk_size=80, overlap=20)
    assert isinstance(splitter, Splitter)
    out = splitter.split("paragraph one.\n\nparagraph two.")
    assert isinstance(out, list)
    assert all(isinstance(p, str) for p in out)


def test_length_fn_tokens():
    """Passing a tokenizer-sized length_fn keeps the chunker correct."""
    from railtracks.retrieval.chunking import TiktokenTokenizer

    tok = TiktokenTokenizer()
    chunker = RecursiveCharacterChunker(
        chunk_size=30, overlap=5, length_fn=tok.count
    )
    text = " ".join(f"word{i}" for i in range(200))
    doc = Document(content=text, type="text/plain")
    chunks = chunker.chunk(doc)
    assert len(chunks) >= 2
    for c in chunks:
        assert tok.count(c.content) <= 30
