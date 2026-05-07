"""Tests for retrieval/stores/models.py — Phase 0 dataclasses and enums."""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from uuid import uuid4

from railtracks.retrieval.models import Chunk, EmbeddedChunk
from railtracks.retrieval.stores.models import (
    DetailLevel,
    MemoryEntry,
    MemoryQuery,
    MemoryScope,
    RetrievalStrategy,
    RetrievedMemoryEntry,
)


def _make_entry(
    user_id: str = "alice",
    content: str = "hello world",
    summary: str = "a summary",
    abstract: str = "an abstract",
) -> MemoryEntry:
    chunk = Chunk(content=content, document_id=uuid4())
    embedded = EmbeddedChunk(chunk=chunk, vector=[0.1, 0.2], embedding_model="toy")
    return MemoryEntry(
        id=uuid4(),
        chunk=embedded,
        abstract=abstract,
        summary=summary,
        scope=MemoryScope(user_id=user_id),
    )


def test_memory_scope_is_frozen():
    scope = MemoryScope(user_id="alice")
    try:
        scope.user_id = "bob"  # type: ignore[misc]
    except FrozenInstanceError:
        return
    raise AssertionError("MemoryScope should be frozen")


def test_memory_scope_as_filter_dict_omits_none():
    scope = MemoryScope(user_id="alice", agent_id="agent-1")
    result = scope.as_filter_dict()
    assert result == {"user_id": "alice", "agent_id": "agent-1"}
    assert "session_id" not in result
    assert "run_id" not in result


def test_memory_scope_as_filter_dict_empty():
    scope = MemoryScope()
    assert scope.as_filter_dict() == {}


def test_memory_entry_stores_all_fields():
    entry = _make_entry()
    assert entry.chunk.chunk.content == "hello world"
    assert entry.abstract == "an abstract"
    assert entry.summary == "a summary"
    assert entry.scope.user_id == "alice"
    assert entry.entities is None
    assert entry.memory_category is None
    assert entry.valid_from is None
    assert entry.valid_until is None


def test_memory_entry_chunk_content_reachable():
    entry = _make_entry(content="deep content")
    assert entry.chunk.chunk.content == "deep content"


def test_memory_query_defaults():
    query = MemoryQuery(text="hello", scope=MemoryScope())
    assert query.strategies == [RetrievalStrategy.VECTOR]
    assert query.detail_level is DetailLevel.L1
    assert query.top_k == 10
    assert query.embedding is None
    assert query.filters == {}


def test_detail_level_l2_value():
    assert DetailLevel.L2.value == "full"


def test_retrieval_strategy_values():
    assert RetrievalStrategy.VECTOR.value == "vector"
    assert RetrievalStrategy.KEYWORD.value == "keyword"
    assert RetrievalStrategy.GRAPH.value == "graph"
    assert RetrievalStrategy.TEMPORAL.value == "temporal"


def test_retrieved_memory_entry():
    entry = _make_entry()
    retrieved = RetrievedMemoryEntry(
        entry=entry, score=0.95, rank=0, source_retriever="dense"
    )
    assert retrieved.score == 0.95
    assert retrieved.rank == 0
    assert retrieved.source_retriever == "dense"
    assert retrieved.rerank_score is None
