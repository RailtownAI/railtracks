"""Tests for retrieval/stores/models.py — Phase 0 dataclasses and enums."""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from uuid import uuid4

from railtracks.retrieval.models import Chunk, EmbeddedChunk
from railtracks.retrieval.stores.models import (
    DetailLevel,
    RetrievalStrategy,
    RetrievedStoreEntry,
    StoreCategory,
    StoreEntry,
    StoreQuery,
    StoreScope,
)


def _make_entry(
    user_id: str = "alice",
    content: str = "hello world",
    summary: str | None = "a summary",
    abstract: str | None = "an abstract",
) -> StoreEntry:
    return StoreEntry(
        id=uuid4(),
        content=content,
        vector=[0.1, 0.2],
        embedding_model="toy",
        chunk_id=uuid4(),
        document_id=uuid4(),
        abstract=abstract,
        summary=summary,
        scope=StoreScope(user_id=user_id),
    )


def test_store_scope_is_frozen():
    scope = StoreScope(user_id="alice")
    try:
        scope.user_id = "bob"  # type: ignore[misc]
    except FrozenInstanceError:
        return
    raise AssertionError("StoreScope should be frozen")


def test_store_scope_to_payload_filters_omits_none():
    scope = StoreScope(user_id="alice", agent_id="agent-1")
    result = scope.to_payload_filters()
    assert result == {"scope_user_id": "alice", "scope_agent_id": "agent-1"}
    assert "scope_session_id" not in result
    assert "scope_run_id" not in result


def test_store_scope_to_payload_filters_empty():
    scope = StoreScope()
    assert scope.to_payload_filters() == {}


def test_store_entry_stores_all_fields():
    entry = _make_entry()
    assert entry.content == "hello world"
    assert entry.abstract == "an abstract"
    assert entry.summary == "a summary"
    assert entry.scope.user_id == "alice"
    assert entry.entities is None
    assert entry.store_category is None
    assert entry.valid_from is None
    assert entry.valid_until is None
    assert entry.created_at is not None


def test_store_entry_optional_fields_default_none():
    entry = StoreEntry(
        id=uuid4(),
        content="x",
        vector=[0.1],
        embedding_model="toy",
        chunk_id=uuid4(),
        document_id=uuid4(),
    )
    assert entry.abstract is None
    assert entry.summary is None
    assert entry.scope is None


def test_store_entry_content_accessible():
    entry = _make_entry(content="deep content")
    assert entry.content == "deep content"


def test_store_entry_from_chunk():
    chunk = Chunk(content="chunk text", document_id=uuid4(), index=3)
    embedded = EmbeddedChunk(chunk=chunk, vector=[0.1, 0.2], embedding_model="toy", embedding_version="v2")
    scope = StoreScope(user_id="alice")

    entry = StoreEntry.from_chunk(
        embedded,
        scope=scope,
        abstract="abs",
        summary="sum",
    )

    assert entry.content == "chunk text"
    assert entry.vector == [0.1, 0.2]
    assert entry.embedding_model == "toy"
    assert entry.embedding_version == "v2"
    assert entry.chunk_id == chunk.id
    assert entry.document_id == chunk.document_id
    assert entry.chunk_index == 3
    assert entry.scope == scope
    assert entry.abstract == "abs"
    assert entry.summary == "sum"
    assert entry.id is not None


def test_store_entry_from_chunk_minimal():
    chunk = Chunk(content="text", document_id=uuid4())
    embedded = EmbeddedChunk(chunk=chunk, vector=[1.0], embedding_model="m")
    entry = StoreEntry.from_chunk(embedded)
    assert entry.scope is None
    assert entry.abstract is None
    assert entry.summary is None


def test_store_query_defaults():
    query = StoreQuery(text="hello", scope=StoreScope())
    assert query.strategies == [RetrievalStrategy.VECTOR]
    assert query.detail_level is DetailLevel.L2
    assert query.top_k == 10
    assert query.embedding is None
    assert query.metadata_filters is None
    assert query.store_category is None


def test_store_category_values():
    assert StoreCategory.EPISODIC.value == "episodic"
    assert StoreCategory.SEMANTIC.value == "semantic"
    assert StoreCategory.SKILL.value == "skill"
    assert StoreCategory.PROCEDURAL.value == "procedural"


def test_store_category_is_str_enum():
    assert StoreCategory("episodic") is StoreCategory.EPISODIC


def test_detail_level_l2_value():
    assert DetailLevel.L2.value == "full"


def test_retrieval_strategy_values():
    assert RetrievalStrategy.VECTOR.value == "vector"
    assert RetrievalStrategy.KEYWORD.value == "keyword"
    assert RetrievalStrategy.GRAPH.value == "graph"
    assert RetrievalStrategy.TEMPORAL.value == "temporal"


def test_retrieved_store_entry():
    entry = _make_entry()
    retrieved = RetrievedStoreEntry(
        entry=entry, score=0.95, rank=0, source_retriever="dense"
    )
    assert retrieved.score == 0.95
    assert retrieved.rank == 0
    assert retrieved.source_retriever == "dense"
    assert retrieved.rerank_score is None
