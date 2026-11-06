"""Sanity checks on the retrieval domain dataclasses."""

from __future__ import annotations

import typing
from uuid import UUID

import railtracks.retrieval.embedding
import railtracks.retrieval.models

from railtracks.retrieval import (
    Chunk,
    Document,
    EmbeddedChunk,
    EmbeddingMetrics,
    RetrievalResult,
    RetrievedChunk,
)


def test_document_defaults():
    doc = Document(content="hello", type="text")
    assert isinstance(doc.id, UUID)
    assert doc.source is None
    assert doc.metadata == {}


def test_chunk_defaults():
    doc = Document(content="c", type="text")
    chunk = Chunk(content="c", document_id=doc.id)
    assert isinstance(chunk.id, UUID)
    assert chunk.index == 0
    assert chunk.parent_chunk_id is None
    assert chunk.offsets is None
    assert chunk.metadata == {}


def test_embedded_retrieved_and_result():
    doc = Document(content="c", type="text")
    chunk = Chunk(content="c", document_id=doc.id)

    embedded = EmbeddedChunk(chunk=chunk, vector=[0.1, 0.2], embedding_model="toy")
    assert embedded.vector == [0.1, 0.2]
    assert embedded.embedding_version is None

    retrieved = RetrievedChunk(chunk=chunk, score=0.9, rank=0)
    assert retrieved.source_retriever is None
    assert retrieved.rerank_score is None

    result = RetrievalResult(query="q", chunks=[retrieved])
    assert result.total_candidates is None
    assert result.metadata == {}
    assert result.embedding_metrics is None


def test_retrieval_result_type_hints_resolve():
    # get_type_hints must not raise NameError; EmbeddingMetrics must not be
    # hidden behind TYPE_CHECKING.
    hints = typing.get_type_hints(RetrievalResult)
    assert EmbeddingMetrics in typing.get_args(hints["embedding_metrics"])


def test_embedding_metrics_same_object_in_retrieval_and_embedding():
    # EmbeddingMetrics lives in retrieval/models.py and is re-exported from
    # retrieval/embedding/models.py; both paths must point to the same class.
    assert (
        railtracks.retrieval.embedding.EmbeddingMetrics
        is railtracks.retrieval.models.EmbeddingMetrics
    )
