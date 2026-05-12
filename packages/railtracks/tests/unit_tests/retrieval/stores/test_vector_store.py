"""Tests for VectorStore + InMemoryBackend — Phase 1."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

import pytest

from railtracks.retrieval.stores.models import (
    DetailLevel,
    MemoryEntry,
    MemoryQuery,
    MemoryScope,
    RetrievalStrategy,
)
from railtracks.retrieval.stores.protocol import Store
from railtracks.retrieval.stores.vector.backends.in_memory import InMemoryBackend
from railtracks.retrieval.stores.vector.base import VectorStore


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_entry(
    user_id: str = "alice",
    content: str = "hello world",
    summary: str = "a summary",
    abstract: str = "an abstract",
    vector: list[float] | None = None,
) -> MemoryEntry:
    if vector is None:
        vector = [1.0, 0.0, 0.0]
    return MemoryEntry(
        id=uuid4(),
        content=content,
        vector=vector,
        embedding_model="toy",
        chunk_id=uuid4(),
        document_id=uuid4(),
        abstract=abstract,
        summary=summary,
        scope=MemoryScope(user_id=user_id),
    )


def _make_query(
    user_id: str = "alice",
    embedding: list[float] | None = None,
    top_k: int = 10,
    detail_level: DetailLevel = DetailLevel.L1,
) -> MemoryQuery:
    if embedding is None:
        embedding = [1.0, 0.0, 0.0]
    return MemoryQuery(
        text="query",
        scope=MemoryScope(user_id=user_id),
        embedding=embedding,
        top_k=top_k,
        detail_level=detail_level,
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


async def test_vector_store_satisfies_store_protocol():
    store = VectorStore(InMemoryBackend())
    assert isinstance(store, Store)


async def test_write_read_roundtrip():
    store = VectorStore(InMemoryBackend())
    entry = _make_entry()

    result_id = await store.write(entry)
    assert result_id == str(entry.id)

    results = await store.read(_make_query())
    assert len(results) == 1
    assert results[0].entry.id == entry.id


async def test_scope_filter_enforcement():
    store = VectorStore(InMemoryBackend())

    entry_alice = _make_entry(user_id="alice", vector=[1.0, 0.0, 0.0])
    entry_bob = _make_entry(user_id="bob", vector=[1.0, 0.0, 0.0])

    await store.write(entry_alice)
    await store.write(entry_bob)

    results = await store.read(_make_query(user_id="alice"))
    assert len(results) == 1
    assert results[0].entry.id == entry_alice.id

    results = await store.read(_make_query(user_id="bob"))
    assert len(results) == 1
    assert results[0].entry.id == entry_bob.id


async def test_detail_level_l0():
    store = VectorStore(InMemoryBackend())
    entry = _make_entry(summary="important summary", content="full content")
    await store.write(entry)

    results = await store.read(_make_query(detail_level=DetailLevel.L0))
    assert len(results) == 1
    assert results[0].entry.summary == ""
    assert results[0].entry.content == ""


async def test_detail_level_l1():
    store = VectorStore(InMemoryBackend())
    entry = _make_entry(summary="important summary", content="full content")
    await store.write(entry)

    results = await store.read(_make_query(detail_level=DetailLevel.L1))
    assert len(results) == 1
    assert results[0].entry.summary == "important summary"
    assert results[0].entry.content == ""


async def test_detail_level_l2():
    store = VectorStore(InMemoryBackend())
    entry = _make_entry(summary="important summary", content="full content")
    await store.write(entry)

    results = await store.read(_make_query(detail_level=DetailLevel.L2))
    assert len(results) == 1
    assert results[0].entry.summary == "important summary"
    assert results[0].entry.content == "full content"


async def test_delete():
    store = VectorStore(InMemoryBackend())
    entry = _make_entry()
    await store.write(entry)

    await store.delete(entry.id)

    results = await store.read(_make_query())
    assert results == []


async def test_clear_scope():
    store = VectorStore(InMemoryBackend())

    scope_a = MemoryScope(user_id="alice")
    scope_b = MemoryScope(user_id="bob")

    entry_a1 = _make_entry(user_id="alice", vector=[1.0, 0.0, 0.0])
    entry_a2 = _make_entry(user_id="alice", vector=[0.0, 1.0, 0.0])
    entry_b = _make_entry(user_id="bob", vector=[1.0, 0.0, 0.0])

    await store.write(entry_a1)
    await store.write(entry_a2)
    await store.write(entry_b)

    await store.clear(scope_a)

    results_a = await store.read(_make_query(user_id="alice"))
    assert results_a == []

    results_b = await store.read(_make_query(user_id="bob"))
    assert len(results_b) == 1
    assert results_b[0].entry.id == entry_b.id


async def test_nearest_neighbors_rank_order():
    store = VectorStore(InMemoryBackend())

    e1 = _make_entry(vector=[1.0, 0.0, 0.0])
    e2 = _make_entry(vector=[0.9, 0.1, 0.0])
    e3 = _make_entry(vector=[0.0, 1.0, 0.0])

    await store.write(e1)
    await store.write(e2)
    await store.write(e3)

    results = await store.nearest_neighbors([1.0, 0.0, 0.0], k=3)
    assert len(results) == 3
    assert results[0].rank == 0
    assert results[1].rank == 1
    assert results[2].rank == 2
    assert results[0].score >= results[1].score >= results[2].score


async def test_cosine_ranking_correctness():
    store = VectorStore(InMemoryBackend())

    near = _make_entry(user_id="alice", vector=[0.9, 0.1, 0.0])
    orthogonal = _make_entry(user_id="alice", vector=[0.0, 0.0, 1.0])

    await store.write(near)
    await store.write(orthogonal)

    results = await store.read(
        _make_query(user_id="alice", embedding=[1.0, 0.0, 0.0])
    )
    assert len(results) == 2
    assert results[0].rank == 0
    assert results[0].entry.id == near.id


async def test_chunk_roundtrip_preserves_all_fields():
    store = VectorStore(InMemoryBackend())

    document_id = uuid4()
    chunk_id = uuid4()
    parent_chunk_id = uuid4()
    entry = MemoryEntry(
        id=uuid4(),
        content="full content",
        vector=[1.0, 0.0, 0.0],
        embedding_model="toy",
        embedding_version="v1",
        chunk_id=chunk_id,
        document_id=document_id,
        chunk_index=7,
        parent_chunk_id=parent_chunk_id,
        chunk_offsets=(12, 48),
        chunk_metadata={"section": "intro", "lang": "en"},
        abstract="abs",
        summary="sum",
        scope=MemoryScope(user_id="alice"),
    )

    await store.write(entry)
    results = await store.read(_make_query(detail_level=DetailLevel.L2))

    assert len(results) == 1
    got = results[0].entry
    assert got.chunk_id == chunk_id
    assert got.document_id == document_id
    assert got.chunk_index == 7
    assert got.parent_chunk_id == parent_chunk_id
    assert got.chunk_offsets == (12, 48)
    assert got.chunk_metadata == {"section": "intro", "lang": "en"}
    assert got.embedding_version == "v1"


async def test_detail_level_preserves_chunk_offsets_and_parent():
    store = VectorStore(InMemoryBackend())

    parent_chunk_id = uuid4()
    entry = MemoryEntry(
        id=uuid4(),
        content="full content",
        vector=[1.0, 0.0, 0.0],
        embedding_model="toy",
        chunk_id=uuid4(),
        document_id=uuid4(),
        parent_chunk_id=parent_chunk_id,
        chunk_offsets=(3, 9),
        abstract="abs",
        summary="sum",
        scope=MemoryScope(user_id="alice"),
    )
    await store.write(entry)

    for level in (DetailLevel.L0, DetailLevel.L1):
        results = await store.read(_make_query(detail_level=level))
        got = results[0].entry
        assert got.content == ""
        assert got.parent_chunk_id == parent_chunk_id
        assert got.chunk_offsets == (3, 9)


async def test_read_raises_without_embedding():
    store = VectorStore(InMemoryBackend())
    query = MemoryQuery(
        text="hello",
        scope=MemoryScope(user_id="alice"),
        embedding=None,
    )
    with pytest.raises(ValueError, match="query.embedding"):
        await store.read(query)


async def test_snapshot_persists_across_instances(tmp_path: Path):
    path = tmp_path / "store.json"

    store_a = VectorStore(InMemoryBackend(snapshot_path=path))
    entry = _make_entry()
    await store_a.write(entry)

    assert path.exists()

    store_b = VectorStore(InMemoryBackend(snapshot_path=path))
    results = await store_b.read(_make_query())
    assert len(results) == 1
    assert results[0].entry.id == entry.id


async def test_snapshot_reflects_deletes(tmp_path: Path):
    path = tmp_path / "store.json"

    store = VectorStore(InMemoryBackend(snapshot_path=path))
    entry = _make_entry()
    await store.write(entry)
    await store.delete(entry.id)

    reloaded = VectorStore(InMemoryBackend(snapshot_path=path))
    results = await reloaded.read(_make_query())
    assert results == []


async def test_snapshot_no_path_leaves_no_file(tmp_path: Path):
    store = VectorStore(InMemoryBackend())
    await store.write(_make_entry())
    assert list(tmp_path.iterdir()) == []


async def test_pgvector_import_error():
    from railtracks.retrieval.stores.vector.backends.pgvector import PgvectorBackend

    backend = PgvectorBackend(dsn="postgresql://localhost/test")

    import builtins

    real_import = builtins.__import__

    def mock_import(name, *args, **kwargs):
        if name == "asyncpg":
            raise ImportError("no module named asyncpg")
        return real_import(name, *args, **kwargs)

    with patch("builtins.__import__", side_effect=mock_import):
        with pytest.raises(ImportError, match="railtracks\\[stores-vector\\]"):
            await backend.initialize()
