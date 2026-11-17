"""Tests for retrieval/stores/models.py — Phase 0 dataclasses and enums."""

from __future__ import annotations

from dataclasses import FrozenInstanceError, fields
from uuid import uuid4

import pytest
from railtracks.retrieval.models import Chunk, EmbeddedChunk
from railtracks.retrieval.stores.models import (
    RetrievedStoreEntry,
    StoreEntry,
    StoreQuery,
    StoreScope,
)


def _make_entry(
    user_id: str = "alice",
    content: str = "hello world",
) -> StoreEntry:
    return StoreEntry(
        id=uuid4(),
        content=content,
        vector=[0.1, 0.2],
        embedding_model="toy",
        chunk_id=uuid4(),
        document_id=uuid4(),
        scope=StoreScope(labels={"user_id": user_id}),
    )


def test_store_scope_is_frozen():
    scope = StoreScope(labels={"user_id": "alice"})
    try:
        scope.labels = {"user_id": "bob"}  # type: ignore[misc]
    except FrozenInstanceError:
        return
    raise AssertionError("StoreScope should be frozen")


def test_store_scope_to_payload_filters_prefixes_keys():
    scope = StoreScope(labels={"user_id": "alice", "agent_id": "agent-1"})
    assert scope.to_payload_filters() == {
        "scope_user_id": "alice",
        "scope_agent_id": "agent-1",
    }


def test_store_scope_to_payload_filters_empty():
    assert StoreScope().to_payload_filters() == {}


def test_store_scope_accepts_arbitrary_dimensions():
    scope = StoreScope(labels={"organization": "acme", "environment": "prod"})
    assert scope.to_payload_filters() == {
        "scope_organization": "acme",
        "scope_environment": "prod",
    }


def test_store_scope_accepts_non_string_scalars():
    scope = StoreScope(labels={"account_id": 42, "is_prod": True})
    assert scope.to_payload_filters() == {
        "scope_account_id": 42,
        "scope_is_prod": True,
    }


def test_store_entry_stores_all_fields():
    entry = _make_entry()
    assert entry.content == "hello world"
    assert entry.scope.labels == {"user_id": "alice"}
    assert entry.created_at is not None


@pytest.mark.parametrize(
    "name", ["abstract", "summary", "entities", "valid_from", "valid_until"]
)
def test_store_entry_has_no_unused_enrichment_fields(name):
    assert name not in {f.name for f in fields(StoreEntry)}


def test_store_entry_optional_fields_default_none():
    entry = StoreEntry(
        id=uuid4(),
        content="x",
        vector=[0.1],
        embedding_model="toy",
        chunk_id=uuid4(),
        document_id=uuid4(),
    )
    assert entry.scope is None
    assert entry.parent_chunk_id is None
    assert entry.embedding_version is None


def test_store_entry_content_accessible():
    entry = _make_entry(content="deep content")
    assert entry.content == "deep content"


def test_store_entry_from_chunk():
    chunk = Chunk(content="chunk text", document_id=uuid4(), index=3)
    embedded = EmbeddedChunk(
        chunk=chunk, vector=[0.1, 0.2], embedding_model="toy", embedding_version="v2"
    )
    scope = StoreScope(labels={"user_id": "alice"})

    entry = StoreEntry.from_chunk(embedded, scope=scope)

    assert entry.content == "chunk text"
    assert entry.vector == [0.1, 0.2]
    assert entry.embedding_model == "toy"
    assert entry.embedding_version == "v2"
    assert entry.chunk_id == chunk.id
    assert entry.document_id == chunk.document_id
    assert entry.chunk_index == 3
    assert entry.scope == scope
    assert entry.id is not None


def test_store_entry_from_chunk_minimal():
    chunk = Chunk(content="text", document_id=uuid4())
    embedded = EmbeddedChunk(chunk=chunk, vector=[1.0], embedding_model="m")
    entry = StoreEntry.from_chunk(embedded)
    assert entry.scope is None


@pytest.mark.parametrize("kwarg", ["abstract", "summary", "entities"])
def test_store_entry_from_chunk_rejects_removed_kwargs(kwarg):
    chunk = Chunk(content="text", document_id=uuid4())
    embedded = EmbeddedChunk(chunk=chunk, vector=[1.0], embedding_model="m")
    with pytest.raises(TypeError):
        StoreEntry.from_chunk(embedded, **{kwarg: "x"})


def test_store_query_defaults():
    query = StoreQuery(text="hello", scope=StoreScope())
    assert query.top_k == 10
    assert query.embedding is None
    assert query.metadata_filters is None


def test_store_query_scope_optional():
    query = StoreQuery(text="hello")
    assert query.scope is None


def test_store_query_text_optional():
    query = StoreQuery(embedding=[0.1, 0.2])
    assert query.text is None
    assert query.embedding == [0.1, 0.2]


def test_retrieved_store_entry():
    entry = _make_entry()
    retrieved = RetrievedStoreEntry(
        entry=entry, score=0.95, rank=0, source_retriever="dense"
    )
    assert retrieved.score == 0.95
    assert retrieved.rank == 0
    assert retrieved.source_retriever == "dense"
    assert retrieved.rerank_score is None


@pytest.mark.parametrize("value", ["alice", 42, 1.5, True])
def test_store_scope_accepts_scalar_label_values(value):
    assert StoreScope(labels={"tenant": value}).labels == {"tenant": value}


@pytest.mark.parametrize(
    ("value", "type_name"),
    [(uuid4(), "UUID"), (None, "NoneType"), (["a"], "list"), ({"a": 1}, "dict")],
)
def test_store_scope_rejects_non_scalar_label_values(value, type_name):
    with pytest.raises(TypeError, match=rf"'tenant' is a {type_name}.*str\(value\)"):
        StoreScope(labels={"tenant": value})


def test_store_scope_rejects_non_str_label_keys():
    with pytest.raises(TypeError, match="label keys must be str"):
        StoreScope(labels={1: "alice"})  # type: ignore[dict-item]
