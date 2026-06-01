"""Tests for SemanticChunker template."""

from __future__ import annotations

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
    assert chunker._identify_breakpoints(distances, chunker.threshold_percentile) == [2]


def test_threshold_percentile_must_be_in_range():
    with pytest.raises(ValueError, match="'threshold_percentile'"):
        SemanticChunker(embedder=_FakeEmbedder(), threshold_percentile=101.0)


def test_create_chunks_with_no_breakpoints():
    chunker = SemanticChunker(embedder=_FakeEmbedder())
    sentences = ["A.", "B.", "C."]
    assert chunker._create_chunks(sentences, []) == ["A. B. C."]


def test_create_chunks_splits_at_breakpoints():
    chunker = SemanticChunker(embedder=_FakeEmbedder())
    sentences = ["A.", "B.", "C.", "D."]
    assert chunker._create_chunks(sentences, [1, 2]) == [
        "A. B.",
        "C.",
        "D.",
    ]


def test_create_chunks_empty_sentences():
    chunker = SemanticChunker(embedder=_FakeEmbedder())
    assert chunker._create_chunks([], [0]) == []
