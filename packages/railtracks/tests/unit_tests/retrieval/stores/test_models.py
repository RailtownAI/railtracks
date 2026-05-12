"""Tests for retrieval/stores/models.py — Phase 0 dataclasses and enums."""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from uuid import uuid4

from railtracks.retrieval.stores.models import (
    DetailLevel,
    MemoryCategory,
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
    return MemoryEntry(
        id=uuid4(),
        content=content,
        vector=[0.1, 0.2],
        embedding_model="toy",
        chunk_id=uuid4(),
        document_id=uuid4(),
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


def test_memory_scope_to_payload_filters_omits_none():
    scope = MemoryScope(user_id="alice", agent_id="agent-1")
    result = scope.to_payload_filters()
    assert result == {"scope_user_id": "alice", "scope_agent_id": "agent-1"}
    assert "scope_session_id" not in result
    assert "scope_run_id" not in result


def test_memory_scope_to_payload_filters_empty():
    scope = MemoryScope()
    assert scope.to_payload_filters() == {}


def test_memory_entry_stores_all_fields():
    entry = _make_entry()
    assert entry.content == "hello world"
    assert entry.abstract == "an abstract"
    assert entry.summary == "a summary"
    assert entry.scope.user_id == "alice"
    assert entry.entities is None
    assert entry.memory_category is None
    assert entry.valid_from is None
    assert entry.valid_until is None
    assert entry.created_at is not None


def test_memory_entry_content_accessible():
    entry = _make_entry(content="deep content")
    assert entry.content == "deep content"


def test_memory_query_defaults():
    query = MemoryQuery(text="hello", scope=MemoryScope())
    assert query.strategies == [RetrievalStrategy.VECTOR]
    assert query.detail_level is DetailLevel.L1
    assert query.top_k == 10
    assert query.embedding is None
    assert query.metadata_filters is None
    assert query.memory_category is None


def test_memory_category_values():
    assert MemoryCategory.EPISODIC.value == "episodic"
    assert MemoryCategory.SEMANTIC.value == "semantic"
    assert MemoryCategory.SKILL.value == "skill"
    assert MemoryCategory.PROCEDURAL.value == "procedural"


def test_memory_category_is_str_enum():
    assert MemoryCategory("episodic") is MemoryCategory.EPISODIC


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
