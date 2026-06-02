"""Tests for SemanticChunker."""

from __future__ import annotations

import asyncio

import pytest

from railtracks.retrieval import Document
from railtracks.retrieval.chunking import Chunker, SemanticChunker
from railtracks.retrieval.embedding import Embedding, EmbeddingMetrics, TextEmbeddings


class _FakeEmbedder(Embedding):
    default_batch_size = 8

    async def aembed(self, texts: list[str]) -> TextEmbeddings:
        return TextEmbeddings(
            vectors=[[float(len(t))] for t in texts],
            metrics=EmbeddingMetrics(vector_count=len(texts)),
        )


def test_semantic_chunker_subclass_chunker_abc():
    assert isinstance(SemanticChunker(embedder=_FakeEmbedder()), Chunker)


def test_empty_document_returns_empty_list(empty_doc):
    assert SemanticChunker(embedder=_FakeEmbedder()).chunk(empty_doc) == []


class _BadLengthEmbedder(Embedding):
    default_batch_size = 8

    async def aembed(self, texts: list[str]) -> TextEmbeddings:
        return TextEmbeddings(vectors=[[0.0]], metrics=EmbeddingMetrics())


def test_embed_vector_count_mismatch_raises():
    doc = Document(content="One. Two.", type="text")
    with pytest.raises(ValueError, match="embedder returned"):
        SemanticChunker(embedder=_BadLengthEmbedder()).chunk(doc)


def test_chunk_produces_chunks_for_document():
    doc = Document(content="First. Second. Third.", type="text")
    chunker = SemanticChunker(embedder=_FakeEmbedder(), threshold_percentile=95.0)
    chunks = chunker.chunk(doc)
    assert chunks
    assert all(c.document_id == doc.id for c in chunks)
    assert [c.index for c in chunks] == list(range(len(chunks)))
    assert "".join(c.content for c in chunks).replace(" ", "") == (
        doc.content.replace(" ", "")
    )


async def test_achunk_matches_sync_chunk():
    doc = Document(content="First. Second. Third.", type="text")
    chunker = SemanticChunker(embedder=_FakeEmbedder(), threshold_percentile=95.0)
    sync_chunks = await asyncio.to_thread(chunker.chunk, doc)
    async_chunks = await chunker.achunk(doc)
    assert [c.content for c in async_chunks] == [c.content for c in sync_chunks]
    assert [c.index for c in async_chunks] == [c.index for c in sync_chunks]


async def test_achunk_empty_document(empty_doc):
    assert await SemanticChunker(embedder=_FakeEmbedder()).achunk(empty_doc) == []


async def test_achunk_uses_aembed_not_embed(monkeypatch):
    doc = Document(content="One. Two.", type="text")
    embedder = _FakeEmbedder()
    chunker = SemanticChunker(embedder=embedder)

    def fail_embed(_texts: list[str]):
        raise AssertionError("achunk should call aembed, not embed")

    monkeypatch.setattr(embedder, "embed", fail_embed)
    await chunker.achunk(doc)


def test_add_context_combines_neighbors():
    chunker = SemanticChunker(
        embedder=_FakeEmbedder(), combine_neighbors=True, window=1
    )
    sentences = ["A.", "B.", "C."]
    assert chunker._add_context(sentences, chunker.window) == [
        "A. B.",
        "A. B. C.",
        "B. C.",
    ]


def test_prepare_embed_inputs_skips_context_when_flag_disabled():
    chunker = SemanticChunker(embedder=_FakeEmbedder(), window=1)
    sentences = ["A.", "B.", "C."]
    assert chunker._prepare_embed_inputs(sentences) == sentences


def test_prepare_embed_inputs_adds_context_when_flag_enabled():
    chunker = SemanticChunker(
        embedder=_FakeEmbedder(), combine_neighbors=True, window=1
    )
    sentences = ["A.", "B.", "C."]
    assert chunker._prepare_embed_inputs(sentences) == [
        "A. B.",
        "A. B. C.",
        "B. C.",
    ]


def test_window_must_be_non_negative():
    with pytest.raises(ValueError, match="'window' must be >= 0"):
        SemanticChunker(embedder=_FakeEmbedder(), window=-1)


def test_calculate_distances_empty_for_single_embedding():
    chunker = SemanticChunker(embedder=_FakeEmbedder())
    assert chunker._calculate_distances([[1.0, 0.0]]) == []


def test_calculate_distances_identical_vectors_are_zero():
    chunker = SemanticChunker(embedder=_FakeEmbedder())
    vec = [1.0, 2.0, 3.0]
    distances = chunker._calculate_distances([vec, vec])
    assert distances == [pytest.approx(0.0)]


def test_calculate_distances_orthogonal_vectors_are_one():
    chunker = SemanticChunker(embedder=_FakeEmbedder())
    distances = chunker._calculate_distances([[1.0, 0.0], [0.0, 1.0]])
    assert distances == [pytest.approx(1.0)]


def test_identify_breakpoints_empty_for_no_distances():
    chunker = SemanticChunker(embedder=_FakeEmbedder())
    assert chunker._identify_breakpoints([], 95.0) == []


def test_identify_breakpoints_finds_outlier_distance():
    chunker = SemanticChunker(embedder=_FakeEmbedder(), threshold_percentile=50.0)
    distances = [0.1, 0.1, 0.9, 0.1]
    assert chunker._identify_breakpoints(distances, chunker.threshold_percentile) == [
        2
    ]


def test_threshold_percentile_must_be_in_range():
    with pytest.raises(ValueError, match="'threshold_percentile'"):
        SemanticChunker(embedder=_FakeEmbedder(), threshold_percentile=101.0)


def test_split_units_uses_split_with_positions():
    chunker = SemanticChunker(embedder=_FakeEmbedder())
    text = "First. Second."
    units = chunker._split_units(text)
    assert units == [("First.", 0, 6), ("Second.", 7, 14)]


def test_offsets_slice_back():
    text = "First. Second! Third? Fourth. Fifth."
    doc = Document(content=text, type="text")
    chunker = SemanticChunker(embedder=_FakeEmbedder(), threshold_percentile=95.0)
    chunks = chunker.chunk(doc)
    for chunk in chunks:
        assert chunk.offsets is not None
        start, end = chunk.offsets
        assert doc.content[start:end] == chunk.content


def test_create_chunks_with_no_breakpoints():
    chunker = SemanticChunker(embedder=_FakeEmbedder())
    text = "A. B. C."
    units = [("A.", 0, 2), ("B.", 3, 5), ("C.", 6, 8)]
    pieces, offsets = chunker._create_chunks(text, units, [])
    assert pieces == ["A. B. C."]
    assert offsets == [(0, 8)]


def test_create_chunks_splits_at_breakpoints():
    chunker = SemanticChunker(embedder=_FakeEmbedder())
    text = "A. B. C. D."
    units = [("A.", 0, 2), ("B.", 3, 5), ("C.", 6, 8), ("D.", 9, 11)]
    pieces, offsets = chunker._create_chunks(text, units, [1, 2])
    assert pieces == ["A. B.", "C.", "D."]
    assert offsets == [(0, 5), (6, 8), (9, 11)]


def test_create_chunks_empty_units():
    chunker = SemanticChunker(embedder=_FakeEmbedder())
    assert chunker._create_chunks("text", [], [0]) == ([], [])
