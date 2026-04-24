"""Sanity checks on the retrieval domain dataclasses."""

from __future__ import annotations

from uuid import UUID

from railtracks.retrieval import (
    Chunk,
    CostBudget,
    Document,
    EmbeddedChunk,
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

    embedded = EmbeddedChunk(
        chunk=chunk, vector=[0.1, 0.2], embedding_model="toy"
    )
    assert embedded.vector == [0.1, 0.2]
    assert embedded.embedding_version is None

    retrieved = RetrievedChunk(chunk=chunk, score=0.9, rank=0)
    assert retrieved.source_retriever is None
    assert retrieved.rerank_score is None

    result = RetrievalResult(query="q", chunks=[retrieved])
    assert result.total_candidates is None
    assert result.metadata == {}


def test_cost_budget_is_frozen():
    budget = CostBudget(tokens=100)
    try:
        budget.tokens = 200  # type: ignore[misc]
    except Exception:
        return
    raise AssertionError("CostBudget should be frozen")
