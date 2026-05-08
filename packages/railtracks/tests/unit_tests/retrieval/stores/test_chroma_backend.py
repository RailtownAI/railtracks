"""Tests for ChromaBackend — mocked, no chromadb install required."""

from __future__ import annotations

import builtins
from unittest.mock import AsyncMock, MagicMock, call, patch
from uuid import uuid4

import pytest

from railtracks.retrieval.models import Chunk, EmbeddedChunk
from railtracks.retrieval.stores.models import (
    DetailLevel,
    MemoryEntry,
    MemoryQuery,
    MemoryScope,
)
from railtracks.retrieval.stores.vector.backends.chroma import (
    ChromaBackend,
    _chroma_to_score,
    _to_chroma_where,
)
from railtracks.retrieval.stores.vector.metric import DistanceMetric
from railtracks.retrieval.stores.vector.base import VectorStore


# ---------------------------------------------------------------------------
# _to_chroma_where
# ---------------------------------------------------------------------------


def test_chroma_where_single_filter():
    result = _to_chroma_where({"scope_user_id": "alice"})
    assert result == {"scope_user_id": {"$eq": "alice"}}


def test_chroma_where_multiple_filters():
    result = _to_chroma_where({"scope_user_id": "alice", "scope_agent_id": "bot"})
    assert result == {
        "$and": [
            {"scope_user_id": {"$eq": "alice"}},
            {"scope_agent_id": {"$eq": "bot"}},
        ]
    }


# ---------------------------------------------------------------------------
# ImportError guard
# ---------------------------------------------------------------------------


async def test_initialize_raises_import_error_without_chromadb():
    backend = ChromaBackend("test")
    real_import = builtins.__import__

    def mock_import(name, *args, **kwargs):
        if name == "chromadb":
            raise ImportError("no module named chromadb")
        return real_import(name, *args, **kwargs)

    with patch("builtins.__import__", side_effect=mock_import):
        with pytest.raises(ImportError, match="railtracks\\[stores-chroma\\]"):
            await backend.initialize()


# ---------------------------------------------------------------------------
# Not-initialized guard
# ---------------------------------------------------------------------------


async def test_not_initialized_raises_on_upsert():
    backend = ChromaBackend("test")
    with pytest.raises(RuntimeError, match="initialize"):
        await backend.upsert("id", [0.1], {})


async def test_not_initialized_raises_on_search():
    backend = ChromaBackend("test")
    with pytest.raises(RuntimeError, match="initialize"):
        await backend.search([0.1], 5, {})


async def test_not_initialized_raises_on_delete():
    backend = ChromaBackend("test")
    with pytest.raises(RuntimeError, match="initialize"):
        await backend.delete("id")


async def test_not_initialized_raises_on_delete_where():
    backend = ChromaBackend("test")
    with pytest.raises(RuntimeError, match="initialize"):
        await backend.delete_where({"scope_user_id": "alice"})


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_collection(count: int = 1) -> MagicMock:
    col = MagicMock()
    col.count.return_value = count
    return col


def _injected_backend(collection: MagicMock) -> ChromaBackend:
    backend = ChromaBackend("test")
    backend._collection = collection
    return backend


def _make_entry(user_id: str = "alice", vector: list[float] | None = None) -> MemoryEntry:
    if vector is None:
        vector = [1.0, 0.0, 0.0]
    chunk = Chunk(content="hello", document_id=uuid4())
    embedded = EmbeddedChunk(chunk=chunk, vector=vector, embedding_model="toy")
    return MemoryEntry(
        id=uuid4(),
        chunk=embedded,
        abstract="abs",
        summary="sum",
        scope=MemoryScope(user_id=user_id),
    )


# ---------------------------------------------------------------------------
# initialize — client selection
# ---------------------------------------------------------------------------


async def test_initialize_uses_ephemeral_client_by_default():
    mock_chroma = MagicMock()
    mock_collection = MagicMock()
    mock_chroma.EphemeralClient.return_value.get_or_create_collection.return_value = (
        mock_collection
    )

    with patch.dict("sys.modules", {"chromadb": mock_chroma}):
        backend = ChromaBackend("my-collection")
        await backend.initialize()

    mock_chroma.EphemeralClient.assert_called_once()
    mock_chroma.EphemeralClient.return_value.get_or_create_collection.assert_called_once_with(
        "my-collection", metadata={"hnsw:space": "cosine"}
    )
    assert backend._collection is mock_collection


async def test_initialize_passes_metric_space_to_collection():
    mock_chroma = MagicMock()
    mock_chroma.EphemeralClient.return_value.get_or_create_collection.return_value = MagicMock()

    with patch.dict("sys.modules", {"chromadb": mock_chroma}):
        backend = ChromaBackend("col", metric=DistanceMetric.L2)
        await backend.initialize()

    mock_chroma.EphemeralClient.return_value.get_or_create_collection.assert_called_once_with(
        "col", metadata={"hnsw:space": "l2"}
    )


async def test_initialize_uses_persistent_client_when_path_given():
    mock_chroma = MagicMock()
    mock_chroma.PersistentClient.return_value.get_or_create_collection.return_value = (
        MagicMock()
    )

    with patch.dict("sys.modules", {"chromadb": mock_chroma}):
        backend = ChromaBackend("col", path="/tmp/chroma")
        await backend.initialize()

    mock_chroma.PersistentClient.assert_called_once_with(path="/tmp/chroma")


async def test_initialize_uses_http_client_when_host_port_given():
    mock_chroma = MagicMock()
    mock_chroma.HttpClient.return_value.get_or_create_collection.return_value = MagicMock()

    with patch.dict("sys.modules", {"chromadb": mock_chroma}):
        backend = ChromaBackend("col", host="localhost", port=8000)
        await backend.initialize()

    mock_chroma.HttpClient.assert_called_once_with(host="localhost", port=8000)


# ---------------------------------------------------------------------------
# upsert
# ---------------------------------------------------------------------------


async def test_upsert_calls_collection_with_correct_args():
    col = _make_collection()
    backend = _injected_backend(col)

    await backend.upsert("entry-1", [0.1, 0.2], {"scope_user_id": "alice"})

    col.upsert.assert_called_once_with(
        ids=["entry-1"],
        embeddings=[[0.1, 0.2]],
        metadatas=[{"scope_user_id": "alice"}],
    )


# ---------------------------------------------------------------------------
# search
# ---------------------------------------------------------------------------


async def test_search_returns_empty_when_collection_is_empty():
    col = _make_collection(count=0)
    backend = _injected_backend(col)

    result = await backend.search([1.0, 0.0], 5, {})

    assert result == []
    col.query.assert_not_called()


async def test_search_caps_n_results_to_collection_count():
    col = _make_collection(count=3)
    col.query.return_value = {
        "ids": [["a", "b", "c"]],
        "distances": [[0.1, 0.2, 0.3]],
        "metadatas": [[{"k": "v1"}, {"k": "v2"}, {"k": "v3"}]],
    }
    backend = _injected_backend(col)

    await backend.search([1.0, 0.0], top_k=10, filters={})

    _, call_kwargs = col.query.call_args
    assert call_kwargs["n_results"] == 3


async def test_search_converts_distance_to_score():
    col = _make_collection(count=2)
    col.query.return_value = {
        "ids": [["a", "b"]],
        "distances": [[0.1, 0.4]],
        "metadatas": [[{"scope_user_id": "alice"}, {"scope_user_id": "alice"}]],
    }
    backend = _injected_backend(col)

    results = await backend.search([1.0, 0.0], top_k=2, filters={})

    assert len(results) == 2
    assert results[0] == ("a", pytest.approx(0.9), {"scope_user_id": "alice"})
    assert results[1] == ("b", pytest.approx(0.6), {"scope_user_id": "alice"})


async def test_search_passes_where_filter():
    col = _make_collection(count=1)
    col.query.return_value = {
        "ids": [["a"]],
        "distances": [[0.0]],
        "metadatas": [[{"scope_user_id": "alice"}]],
    }
    backend = _injected_backend(col)

    await backend.search([1.0, 0.0], top_k=5, filters={"scope_user_id": "alice"})

    _, call_kwargs = col.query.call_args
    assert call_kwargs["where"] == {"scope_user_id": {"$eq": "alice"}}


def test_chroma_to_score_cosine():
    assert _chroma_to_score(DistanceMetric.COSINE, 0.1) == pytest.approx(0.9)
    assert _chroma_to_score(DistanceMetric.COSINE, 0.0) == pytest.approx(1.0)


def test_chroma_to_score_l2_applies_sqrt():
    # Chroma returns squared L2; score = 1 / (1 + sqrt(d))
    import math
    assert _chroma_to_score(DistanceMetric.L2, 0.0) == pytest.approx(1.0)
    assert _chroma_to_score(DistanceMetric.L2, 1.0) == pytest.approx(0.5)
    assert _chroma_to_score(DistanceMetric.L2, 4.0) == pytest.approx(1.0 / 3.0)


def test_chroma_to_score_ip():
    # Chroma ip: distance = 1 - dot_product → score = 1 - distance = dot_product
    assert _chroma_to_score(DistanceMetric.IP, 0.3) == pytest.approx(0.7)


async def test_search_passes_no_where_when_filters_empty():
    col = _make_collection(count=1)
    col.query.return_value = {"ids": [["a"]], "distances": [[0.0]], "metadatas": [[{}]]}
    backend = _injected_backend(col)

    await backend.search([1.0, 0.0], top_k=5, filters={})

    _, call_kwargs = col.query.call_args
    assert call_kwargs["where"] is None


# ---------------------------------------------------------------------------
# delete
# ---------------------------------------------------------------------------


async def test_delete_calls_collection_delete_with_id():
    col = _make_collection()
    backend = _injected_backend(col)

    await backend.delete("entry-1")

    col.delete.assert_called_once_with(ids=["entry-1"])


# ---------------------------------------------------------------------------
# delete_where
# ---------------------------------------------------------------------------


async def test_delete_where_calls_collection_with_where_clause():
    col = _make_collection()
    backend = _injected_backend(col)

    await backend.delete_where({"scope_user_id": "alice"})

    col.delete.assert_called_once_with(where={"scope_user_id": {"$eq": "alice"}})


async def test_delete_where_empty_filters_is_noop():
    col = _make_collection()
    backend = _injected_backend(col)

    await backend.delete_where({})

    col.delete.assert_not_called()


# ---------------------------------------------------------------------------
# VectorStore integration (via mocked ChromaBackend)
# ---------------------------------------------------------------------------


async def test_vector_store_write_read_via_chroma():
    """Full VectorStore round-trip using ChromaBackend with a mocked collection."""
    entry = _make_entry(vector=[1.0, 0.0, 0.0])

    from railtracks.retrieval.stores.vector.base import _entry_to_payload

    payload = _entry_to_payload(entry)

    col = MagicMock()
    col.count.return_value = 1
    col.query.return_value = {
        "ids": [[str(entry.id)]],
        "distances": [[0.05]],
        "metadatas": [[payload]],
    }

    store = VectorStore(_injected_backend(col))
    write_id = await store.write(entry)
    assert write_id == str(entry.id)

    results = await store.read(
        MemoryQuery(
            text="q",
            scope=MemoryScope(user_id="alice"),
            embedding=[1.0, 0.0, 0.0],
            detail_level=DetailLevel.L2,
        )
    )

    assert len(results) == 1
    assert results[0].entry.id == entry.id
    assert results[0].score == pytest.approx(0.95)
    assert results[0].entry.chunk.chunk.content == "hello"
