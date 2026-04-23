"""Tests for FixedTokenChunker."""

from __future__ import annotations

import pytest

from railtracks.retrieval import Document
from railtracks.retrieval.chunking import FixedTokenChunker, TiktokenTokenizer


def test_checklist(chunker_checklist, multi_paragraph_doc, short_doc, empty_doc):
    chunker_checklist(
        lambda: FixedTokenChunker(chunk_size=50, overlap=10),
        multi_paragraph_doc,
        short_doc,
        empty_doc,
    )


def test_offsets_are_none_by_design(multi_paragraph_doc):
    chunker = FixedTokenChunker(chunk_size=40, overlap=10)
    chunks = chunker.chunk(multi_paragraph_doc)
    assert len(chunks) >= 2
    assert all(c.offsets is None for c in chunks)


def test_overlap_window_matches_expected_tokens():
    chunker = FixedTokenChunker(chunk_size=8, overlap=3)
    text = " ".join(f"w{i}" for i in range(40))
    doc = Document(content=text, type="text/plain")
    chunks = chunker.chunk(doc)
    encoded = [chunker.tokenizer.encode(c.content) for c in chunks]
    for i in range(len(encoded) - 1):
        a, b = encoded[i], encoded[i + 1]
        if len(a) >= 8 and len(b) >= 8:
            assert a[-3:] == b[:3]


def test_zero_overlap_produces_contiguous_chunks():
    chunker = FixedTokenChunker(chunk_size=5, overlap=0)
    text = "one two three four five six seven eight nine ten"
    doc = Document(content=text, type="text/plain")
    chunks = chunker.chunk(doc)
    total_tokens = sum(chunker.tokenizer.count(c.content) for c in chunks)
    assert total_tokens == chunker.tokenizer.count(text)


def test_rejects_invalid_construction():
    with pytest.raises(ValueError):
        FixedTokenChunker(chunk_size=0)
    with pytest.raises(ValueError):
        FixedTokenChunker(chunk_size=10, overlap=-1)
    with pytest.raises(ValueError):
        FixedTokenChunker(chunk_size=10, overlap=10)
    with pytest.raises(ValueError):
        FixedTokenChunker(chunk_size=10, overlap=11)


def test_injected_tokenizer():
    custom = TiktokenTokenizer("cl100k_base")
    chunker = FixedTokenChunker(chunk_size=20, overlap=5, tokenizer=custom)
    assert chunker.tokenizer is custom
