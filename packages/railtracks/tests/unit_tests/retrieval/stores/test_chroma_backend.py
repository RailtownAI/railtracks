"""Tests for ChromaBackend and ChromaCloudBackend — mocked, no chromadb install required."""

from __future__ import annotations

import builtins
from unittest.mock import MagicMock, PropertyMock, patch
from uuid import uuid4

import pytest
from railtracks.retrieval.stores.models import (
    StoreEntry,
    StoreQuery,
    StoreScope,
)
from railtracks.retrieval.stores.vector.backends.chroma import (
    ChromaBackend,
    ChromaCloudBackend,
    _chroma_to_score,
    _collection_space,
    _to_chroma_where,
)
from railtracks.retrieval.stores.vector.base import VectorStore
from railtracks.retrieval.stores.vector.metric import DistanceMetric

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


def _space_collection(space: str = "cosine", index: str = "hnsw") -> MagicMock:
    """A mocked collection as returned by get_or_create_collection, whose raw
    configuration reports ``space`` for the given index type."""
    col = MagicMock()
    col.configuration_json = {index: {"space": space}}
    col.metadata = None
    return col


def _injected_backend(collection: MagicMock) -> ChromaBackend:
    backend = ChromaBackend("test")
    backend._collection = collection
    return backend


def _make_entry(
    user_id: str = "alice", vector: list[float] | None = None
) -> StoreEntry:
    if vector is None:
        vector = [1.0, 0.0, 0.0]
    return StoreEntry(
        id=uuid4(),
        content="hello",
        vector=vector,
        embedding_model="toy",
        chunk_id=uuid4(),
        document_id=uuid4(),
        abstract="abs",
        summary="sum",
        scope=StoreScope(labels={"user_id": user_id}),
    )


# ---------------------------------------------------------------------------
# initialize — client selection
# ---------------------------------------------------------------------------


async def test_initialize_uses_ephemeral_client_by_default():
    mock_chroma = MagicMock()
    mock_collection = _space_collection()
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
    mock_chroma.EphemeralClient.return_value.get_or_create_collection.return_value = (
        _space_collection("l2")
    )

    with patch.dict("sys.modules", {"chromadb": mock_chroma}):
        backend = ChromaBackend("col", metric=DistanceMetric.L2)
        await backend.initialize()

    mock_chroma.EphemeralClient.return_value.get_or_create_collection.assert_called_once_with(
        "col", metadata={"hnsw:space": "l2"}
    )


async def test_initialize_uses_persistent_client_when_path_given():
    mock_chroma = MagicMock()
    mock_chroma.PersistentClient.return_value.get_or_create_collection.return_value = (
        _space_collection()
    )

    with patch.dict("sys.modules", {"chromadb": mock_chroma}):
        backend = ChromaBackend("col", path="/tmp/chroma")
        await backend.initialize()

    mock_chroma.PersistentClient.assert_called_once_with(path="/tmp/chroma")


async def test_initialize_uses_http_client_when_host_port_given():
    mock_chroma = MagicMock()
    mock_chroma.HttpClient.return_value.get_or_create_collection.return_value = (
        _space_collection()
    )

    with patch.dict("sys.modules", {"chromadb": mock_chroma}):
        backend = ChromaBackend("col", host="localhost", port=8000)
        await backend.initialize()

    mock_chroma.HttpClient.assert_called_once_with(host="localhost", port=8000)


# ---------------------------------------------------------------------------
# initialize — collection distance space must match metric (#1665)
# ---------------------------------------------------------------------------


async def test_initialize_raises_when_existing_collection_space_differs():
    mock_chroma = MagicMock()
    mock_chroma.EphemeralClient.return_value.get_or_create_collection.return_value = (
        _space_collection("l2")
    )

    backend = ChromaBackend("col")  # cosine by default
    with patch.dict("sys.modules", {"chromadb": mock_chroma}):
        with pytest.raises(ValueError, match="'col' uses the 'l2' distance space"):
            await backend.initialize()

    assert backend._collection is None


def test_collection_space_reads_spann_config():
    col = _space_collection("cosine", index="spann")
    assert _collection_space(col) == "cosine"


def test_collection_space_reads_hnsw_config():
    col = _space_collection("ip", index="hnsw")
    assert _collection_space(col) == "ip"


def test_collection_space_prefers_configured_index_over_empty_one():
    col = MagicMock()
    col.configuration_json = {"hnsw": None, "spann": {"space": "cosine"}}
    col.metadata = None
    assert _collection_space(col) == "cosine"


def test_collection_space_falls_back_to_metadata():
    col = MagicMock()
    col.configuration_json = {}
    col.metadata = {"hnsw:space": "cosine"}
    assert _collection_space(col) == "cosine"


def test_collection_space_defaults_to_l2():
    col = MagicMock()
    col.configuration_json = None
    col.metadata = None
    assert _collection_space(col) == "l2"


def test_collection_space_never_reads_parsed_configuration():
    # collection.configuration rebuilds the stored embedding function and
    # raises for some Cloud collections; only the raw JSON may be read.
    col = _space_collection("cosine", index="spann")
    type(col).configuration = PropertyMock(
        side_effect=ValueError("Could not build embedding function")
    )
    assert _collection_space(col) == "cosine"


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
        documents=None,
        metadatas=[{"scope_user_id": "alice"}],
    )


async def test_upsert_stores_content_only_as_document():
    col = _make_collection()
    backend = _injected_backend(col)
    payload = {"content": "hello world", "scope_user_id": "alice"}

    await backend.upsert("entry-1", [0.1, 0.2], payload)

    col.upsert.assert_called_once_with(
        ids=["entry-1"],
        embeddings=[[0.1, 0.2]],
        documents=["hello world"],
        metadatas=[{"scope_user_id": "alice"}],
    )
    assert payload == {"content": "hello world", "scope_user_id": "alice"}


async def test_upsert_omits_metadatas_when_payload_is_only_content():
    col = _make_collection()
    backend = _injected_backend(col)

    await backend.upsert("entry-1", [0.1, 0.2], {"content": "hello world"})

    col.upsert.assert_called_once_with(
        ids=["entry-1"],
        embeddings=[[0.1, 0.2]],
        documents=["hello world"],
        metadatas=None,
    )


# ---------------------------------------------------------------------------
# search
# ---------------------------------------------------------------------------


async def test_search_returns_empty_when_nothing_matches():
    col = _make_collection()
    col.query.return_value = {
        "ids": [[]],
        "distances": [[]],
        "metadatas": [[]],
        "documents": [[]],
    }
    backend = _injected_backend(col)

    assert await backend.search([1.0, 0.0], 5, {}) == []


async def test_search_passes_top_k_without_counting():
    col = _make_collection()
    col.query.return_value = {
        "ids": [["a", "b", "c"]],
        "distances": [[0.1, 0.2, 0.3]],
        "metadatas": [[{"k": "v1"}, {"k": "v2"}, {"k": "v3"}]],
        "documents": [[None, None, None]],
    }
    backend = _injected_backend(col)

    await backend.search([1.0, 0.0], top_k=10, filters={})

    _, call_kwargs = col.query.call_args
    assert call_kwargs["n_results"] == 10
    col.count.assert_not_called()


async def test_search_converts_distance_to_score():
    col = _make_collection(count=2)
    col.query.return_value = {
        "ids": [["a", "b"]],
        "distances": [[0.1, 0.4]],
        "metadatas": [[{"scope_user_id": "alice"}, {"scope_user_id": "alice"}]],
        "documents": [[None, None]],
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
        "documents": [[None]],
    }
    backend = _injected_backend(col)

    await backend.search([1.0, 0.0], top_k=5, filters={"scope_user_id": "alice"})

    _, call_kwargs = col.query.call_args
    assert call_kwargs["where"] == {"scope_user_id": {"$eq": "alice"}}


async def test_search_restores_content_from_documents():
    col = _make_collection(count=1)
    col.query.return_value = {
        "ids": [["a"]],
        "distances": [[0.0]],
        "metadatas": [[{"scope_user_id": "alice"}]],
        "documents": [["hello world"]],
    }
    backend = _injected_backend(col)

    hits = await backend.search([1.0, 0.0], top_k=5, filters={})

    assert hits == [
        ("a", pytest.approx(1.0), {"scope_user_id": "alice", "content": "hello world"})
    ]
    _, call_kwargs = col.query.call_args
    assert "documents" in call_kwargs["include"]


def test_chroma_to_score_cosine():
    assert _chroma_to_score(DistanceMetric.COSINE, 0.1) == pytest.approx(0.9)
    assert _chroma_to_score(DistanceMetric.COSINE, 0.0) == pytest.approx(1.0)


def test_chroma_to_score_l2_applies_sqrt():
    # Chroma returns squared L2; score = 1 / (1 + sqrt(d))
    assert _chroma_to_score(DistanceMetric.L2, 0.0) == pytest.approx(1.0)
    assert _chroma_to_score(DistanceMetric.L2, 1.0) == pytest.approx(0.5)
    assert _chroma_to_score(DistanceMetric.L2, 4.0) == pytest.approx(1.0 / 3.0)


def test_chroma_to_score_ip():
    # Chroma ip: distance = 1 - dot_product → score = 1 - distance = dot_product
    assert _chroma_to_score(DistanceMetric.IP, 0.3) == pytest.approx(0.7)


async def test_search_passes_no_where_when_filters_empty():
    col = _make_collection(count=1)
    col.query.return_value = {
        "ids": [["a"]],
        "distances": [[0.0]],
        "metadatas": [[{}]],
        "documents": [[None]],
    }
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

    col = MagicMock()
    col.count.return_value = 1

    store = VectorStore(_injected_backend(col))
    write_id = await store.write(entry)
    assert write_id == str(entry.id)

    # Serve back exactly what was written to Chroma.
    stored = col.upsert.call_args.kwargs
    assert "content" not in stored["metadatas"][0]
    assert stored["metadatas"][0] == {
        k: v for k, v in _entry_to_payload(entry).items() if k != "content"
    }
    col.query.return_value = {
        "ids": [stored["ids"]],
        "distances": [[0.05]],
        "metadatas": [stored["metadatas"]],
        "documents": [stored["documents"]],
    }

    results = await store.read(
        StoreQuery(
            text="q",
            scope=StoreScope(labels={"user_id": "alice"}),
            embedding=[1.0, 0.0, 0.0],
        )
    )

    assert len(results) == 1
    assert results[0].entry.id == entry.id
    assert results[0].score == pytest.approx(0.95)
    assert results[0].entry.content == "hello"


# ---------------------------------------------------------------------------
# ChromaCloudBackend helpers
# ---------------------------------------------------------------------------


def _cloud_backend(collection: MagicMock | None = None) -> ChromaCloudBackend:
    backend = ChromaCloudBackend(
        "my-collection",
        api_key="chk-key",
        tenant="my-tenant",
        database="my-db",
    )
    backend._collection = collection
    return backend


# ---------------------------------------------------------------------------
# ChromaCloudBackend — not-initialized guard
# ---------------------------------------------------------------------------


async def test_cloud_not_initialized_raises_on_upsert():
    backend = _cloud_backend(collection=None)
    with pytest.raises(RuntimeError, match="initialize"):
        await backend.upsert("id", [0.1], {})


async def test_cloud_not_initialized_raises_on_search():
    backend = _cloud_backend(collection=None)
    with pytest.raises(RuntimeError, match="initialize"):
        await backend.search([0.1], 5, {})


async def test_cloud_not_initialized_raises_on_delete():
    backend = _cloud_backend(collection=None)
    with pytest.raises(RuntimeError, match="initialize"):
        await backend.delete("id")


async def test_cloud_not_initialized_raises_on_delete_where():
    backend = _cloud_backend(collection=None)
    with pytest.raises(RuntimeError, match="initialize"):
        await backend.delete_where({"scope_user_id": "alice"})


# ---------------------------------------------------------------------------
# ChromaCloudBackend — ImportError guard
# ---------------------------------------------------------------------------


async def test_cloud_initialize_raises_import_error_without_chromadb():
    backend = _cloud_backend(collection=None)
    real_import = builtins.__import__

    def mock_import(name, *args, **kwargs):
        if name == "chromadb":
            raise ImportError("no module named chromadb")
        return real_import(name, *args, **kwargs)

    with patch("builtins.__import__", side_effect=mock_import):
        with pytest.raises(ImportError, match="railtracks\\[stores-chroma\\]"):
            await backend.initialize()


# ---------------------------------------------------------------------------
# ChromaCloudBackend — initialize: uses CloudClient, not EphemeralClient
# ---------------------------------------------------------------------------


async def test_cloud_initialize_uses_cloud_client():
    mock_chroma = MagicMock()
    mock_collection = _space_collection()
    mock_chroma.CloudClient.return_value.get_or_create_collection.return_value = (
        mock_collection
    )

    backend = ChromaCloudBackend(
        "my-collection",
        api_key="chk-key",
        tenant="my-tenant",
        database="my-db",
    )

    with patch.dict("sys.modules", {"chromadb": mock_chroma}):
        await backend.initialize()

    mock_chroma.CloudClient.assert_called_once_with(
        api_key="chk-key",
        tenant="my-tenant",
        database="my-db",
    )
    assert backend._collection is mock_collection


async def test_cloud_initialize_sets_metric_space_on_collection():
    mock_chroma = MagicMock()
    mock_chroma.CloudClient.return_value.get_or_create_collection.return_value = (
        _space_collection("l2", index="spann")
    )

    backend = ChromaCloudBackend(
        "my-collection",
        api_key="chk-key",
        tenant="my-tenant",
        database="my-db",
        metric=DistanceMetric.L2,
    )

    with patch.dict("sys.modules", {"chromadb": mock_chroma}):
        await backend.initialize()

    mock_chroma.CloudClient.return_value.get_or_create_collection.assert_called_once_with(
        "my-collection", metadata={"hnsw:space": "l2"}
    )


async def test_cloud_initialize_raises_when_existing_collection_space_differs():
    mock_chroma = MagicMock()
    mock_chroma.CloudClient.return_value.get_or_create_collection.return_value = (
        _space_collection("l2", index="spann")
    )

    backend = _cloud_backend(collection=None)  # cosine by default
    with patch.dict("sys.modules", {"chromadb": mock_chroma}):
        with pytest.raises(ValueError, match="uses the 'l2' distance space"):
            await backend.initialize()

    assert backend._collection is None


async def test_cloud_initialize_does_not_call_ephemeral_or_http_client():
    mock_chroma = MagicMock()
    mock_chroma.CloudClient.return_value.get_or_create_collection.return_value = (
        _space_collection()
    )

    backend = ChromaCloudBackend("col", api_key="k", tenant="t", database="d")

    with patch.dict("sys.modules", {"chromadb": mock_chroma}):
        await backend.initialize()

    mock_chroma.EphemeralClient.assert_not_called()
    mock_chroma.HttpClient.assert_not_called()
    mock_chroma.PersistentClient.assert_not_called()


# ---------------------------------------------------------------------------
# ChromaCloudBackend — create() factory
# ---------------------------------------------------------------------------


async def test_cloud_create_factory_returns_initialized_backend():
    mock_chroma = MagicMock()
    mock_chroma.CloudClient.return_value.get_or_create_collection.return_value = (
        _space_collection()
    )

    with patch.dict("sys.modules", {"chromadb": mock_chroma}):
        backend = await ChromaCloudBackend.create(
            "my-collection",
            api_key="chk-key",
            tenant="my-tenant",
            database="my-db",
        )

    assert isinstance(backend, ChromaCloudBackend)
    assert backend._collection is not None


# ---------------------------------------------------------------------------
# Paged get — Chroma Cloud caps the per-request limit value (#1180)
# ---------------------------------------------------------------------------


def _paging_collection(total: int) -> MagicMock:
    """A mocked collection holding ``total`` entries whose get() enforces the
    Chroma Cloud per-request limit quota, mirroring the error from #1180."""
    ids = [f"id-{i}" for i in range(total)]
    metadatas = [{"i": i} for i in range(total)]
    documents = [f"doc-{i}" for i in range(total)]

    def fake_get(where=None, limit=None, offset=0, include=None):
        if limit is not None and limit > 300:
            raise RuntimeError(
                "Quota exceeded: 'Limit value' exceeded quota limit for "
                f"action 'Get': current usage of {limit} exceeds limit of 300"
            )
        end = total if limit is None else min(offset + limit, total)
        return {
            "ids": ids[offset:end],
            "metadatas": (
                metadatas[offset:end] if include and "metadatas" in include else None
            ),
            "documents": (
                documents[offset:end] if include and "documents" in include else None
            ),
        }

    col = MagicMock()
    col.get.side_effect = fake_get
    return col


async def test_list_where_pages_large_limits_under_cloud_cap():
    collection = _paging_collection(total=1056)
    backend = _injected_backend(collection)

    rows = await backend.list_where({"source_path": "doc"}, limit=1056)

    assert len(rows) == 1056
    assert rows[0] == ("id-0", {"i": 0, "content": "doc-0"})
    assert rows[-1] == ("id-1055", {"i": 1055, "content": "doc-1055"})
    # Every underlying get stayed at or under the per-request cap.
    assert all(c.kwargs["limit"] <= 300 for c in collection.get.call_args_list)


async def test_list_where_stops_at_requested_limit():
    collection = _paging_collection(total=1000)
    backend = _injected_backend(collection)

    rows = await backend.list_where({"source_path": "doc"}, limit=5)

    assert len(rows) == 5
    assert collection.get.call_count == 1
    assert collection.get.call_args.kwargs["limit"] == 5


async def test_filtered_count_pages_to_exhaustion():
    collection = _paging_collection(total=750)
    backend = _injected_backend(collection)

    assert await backend.count({"source_path": "doc"}) == 750
    assert all(c.kwargs["limit"] <= 300 for c in collection.get.call_args_list)
    # ids only — no payload transfer just to count.
    assert all(c.kwargs["include"] == [] for c in collection.get.call_args_list)


async def test_unfiltered_count_uses_collection_count():
    collection = _make_collection(count=42)
    backend = _injected_backend(collection)

    assert await backend.count({}) == 42
    collection.get.assert_not_called()


# ---------------------------------------------------------------------------
# Real chromadb — distance space round-trip (#1665). Skipped without chromadb.
# ---------------------------------------------------------------------------


async def test_real_chroma_new_collection_gets_metric_space(tmp_path):
    pytest.importorskip("chromadb")
    backend = await ChromaBackend.create("col", path=str(tmp_path))

    await backend.upsert("a", [1.0, 0.0], {"k": 1})
    await backend.upsert("b", [0.0, 1.0], {"k": 2})
    hits = await backend.search([1.0, 0.0], 2, {})

    assert _collection_space(backend._collection) == "cosine"
    scores = {id_: score for id_, score, _ in hits}
    assert scores["a"] == pytest.approx(1.0)
    assert scores["b"] == pytest.approx(0.0)  # orthogonal, not -1.0 as under l2


async def test_real_chroma_existing_collection_with_other_space_raises(tmp_path):
    chromadb = pytest.importorskip("chromadb")
    chromadb.PersistentClient(path=str(tmp_path)).get_or_create_collection(
        "col", metadata={"hnsw:space": "l2"}
    )

    with pytest.raises(ValueError, match="'col' uses the 'l2' distance space"):
        await ChromaBackend.create("col", path=str(tmp_path))

    # The matching metric opens it fine.
    backend = await ChromaBackend.create(
        "col", path=str(tmp_path), metric=DistanceMetric.L2
    )
    assert backend._collection is not None


async def test_real_chroma_content_stored_once_and_round_trips(tmp_path):
    pytest.importorskip("chromadb")
    backend = await ChromaBackend.create("col", path=str(tmp_path))

    await backend.upsert("a", [1.0, 0.0], {"content": "hello", "k": 1})

    raw = backend._collection.get(ids=["a"], include=["metadatas", "documents"])
    assert raw["documents"] == ["hello"]
    assert raw["metadatas"] == [{"k": 1}]

    hits = await backend.search([1.0, 0.0], 1, {})
    assert hits[0][2] == {"k": 1, "content": "hello"}
    assert await backend.list_where({"k": 1}, 10) == [
        ("a", {"k": 1, "content": "hello"})
    ]


async def test_real_chroma_search_handles_empty_and_oversized_top_k(tmp_path):
    pytest.importorskip("chromadb")
    backend = await ChromaBackend.create("col", path=str(tmp_path))

    assert await backend.search([1.0, 0.0], 5, {}) == []

    await backend.upsert("a", [1.0, 0.0], {"k": 1})
    await backend.upsert("b", [0.0, 1.0], {"k": 2})
    assert len(await backend.search([1.0, 0.0], 10, {})) == 2
    assert [h[0] for h in await backend.search([1.0, 0.0], 10, {"k": 2})] == ["b"]
    assert await backend.search([1.0, 0.0], 10, {"k": 3}) == []
