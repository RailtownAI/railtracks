"""Tests for SentenceChunker."""

from __future__ import annotations

import pytest

from railtracks.retrieval import Document
from railtracks.retrieval.chunking import RegexSentenceSplitter, SentenceChunker


def test_checklist(chunker_checklist, multi_paragraph_doc, short_doc, empty_doc):
    chunker_checklist(
        lambda: SentenceChunker(chunk_size=2, overlap=1),
        multi_paragraph_doc,
        short_doc,
        empty_doc,
    )


def test_sentence_count_metadata():
    text = "Alpha. Beta. Gamma. Delta. Epsilon. Zeta. Eta."
    doc = Document(content=text, type="text/plain")
    chunker = SentenceChunker(chunk_size=3, overlap=1)
    chunks = chunker.chunk(doc)
    assert all("sentence_count" in c.metadata for c in chunks)
    # 7 sentences, size=3, overlap=1, step=2 -> windows [0..3), [2..5),
    # [4..7). The final window reaches the end so we stop (no trailing
    # duplicate-suffix chunk).
    assert [c.metadata["sentence_count"] for c in chunks] == [3, 3, 3]


def test_offsets_slice_back():
    text = "First. Second! Third? Fourth. Fifth."
    doc = Document(content=text, type="text/plain")
    chunker = SentenceChunker(chunk_size=2, overlap=0)
    chunks = chunker.chunk(doc)
    for c in chunks:
        s, e = c.offsets
        assert doc.content[s:e] == c.content


def test_rejects_invalid_construction():
    with pytest.raises(ValueError):
        SentenceChunker(chunk_size=0)
    with pytest.raises(ValueError):
        SentenceChunker(chunk_size=2, overlap=2)
    with pytest.raises(ValueError):
        SentenceChunker(chunk_size=2, overlap=-1)


def test_custom_splitter_via_protocol():
    class UpperCaseSplitter:
        def split(self, text: str) -> list[str]:
            return [s.strip() for s in text.split(".") if s.strip()]

    text = "Alpha. Beta. Gamma. Delta."
    doc = Document(content=text, type="text/plain")
    chunker = SentenceChunker(chunk_size=2, overlap=0, sentence_splitter=UpperCaseSplitter())
    chunks = chunker.chunk(doc)
    assert len(chunks) == 2


def test_regex_sentence_splitter_returns_sentences():
    splitter = RegexSentenceSplitter()
    out = splitter.split("First one. Second! Third?")
    assert out == ["First one.", "Second!", "Third?"]
