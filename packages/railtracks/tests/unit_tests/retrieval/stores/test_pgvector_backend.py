"""Tests for PgvectorBackend — mocked, no postgres install required."""

from __future__ import annotations

import json
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from railtracks.retrieval.stores.models import (
    DetailLevel,
    StoreEntry,
    StoreQuery,
    StoreScope,
)
from railtracks.retrieval.stores.vector.backends.pgvector import (
    PgvectorBackend,
    _build_where,
    _pg_to_score,
)
from railtracks.retrieval.stores.vector.base import VectorStore
from railtracks.retrieval.stores.vector.metric import DistanceMetric

# ---------------------------------------------------------------------------
# _build_where
# ---------------------------------------------------------------------------


def test_build_where_empty():
    clause, params = _build_where({})
    assert clause == ""
    assert params == []


def test_build_where_single():
    clause, params = _build_where({"scope_user_id": "alice"})
    assert clause == "WHERE payload->$1::text = $2::jsonb"
    assert params == ["scope_user_id", json.dumps("alice")]


def test_build_where_multiple():
    clause, params = _build_where(
        {"scope_user_id": "alice", "scope_agent_id": "bot"}
    )
    assert "payload->$1::text = $2::jsonb" in clause
    assert "payload->$3::text = $4::jsonb" in clause
    assert params == [
        "scope_user_id",
        json.dumps("alice"),
        "scope_agent_id",
        json.dumps("bot"),
    ]


def test_build_where_respects_start_index():
    clause, params = _build_where({"scope_user_id": "alice"}, start_index=2)
    assert clause == "WHERE payload->$2::text = $3::jsonb"
    assert params == ["scope_user_id", json.dumps("alice")]


def test_build_where_preserves_jsonb_types_for_non_string_values():
    """Booleans, integers, floats, and None must round-trip as their JSONB
    type — not be coerced to Python's str() form (e.g. ``True`` -> ``'True'``)
    which JSONB renders as ``'true'`` and would never match."""
    clause, params = _build_where({"page": 3, "active": True, "tag": None})
    # Each value is JSON-encoded so the comparison is JSONB-to-JSONB.
    assert params == ["page", "3", "active", "true", "tag", "null"]
    assert "payload->$1::text = $2::jsonb" in clause
    assert "payload->$3::text = $4::jsonb" in clause
    assert "payload->$5::text = $6::jsonb" in clause


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_pool() -> tuple[AsyncMock, MagicMock]:
    """Return (mock_conn, mock_pool) where pool.acquire() is an async CM."""
    conn = AsyncMock()
    conn.fetch = AsyncMock(return_value=[])

    pool = MagicMock()

    @asynccontextmanager
    async def _acquire():
        yield conn

    pool.acquire = _acquire
    return conn, pool


def _injected_backend(pool) -> PgvectorBackend:
    backend = PgvectorBackend("postgresql://test/test")
    backend._pool = pool
    return backend


def _make_entry(user_id: str = "alice", vector: list[float] | None = None) -> StoreEntry:
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
        scope=StoreScope(user_id=user_id),
    )


# ---------------------------------------------------------------------------
# Not-initialized guard
# ---------------------------------------------------------------------------


async def test_not_initialized_raises_on_upsert():
    backend = PgvectorBackend("postgresql://test/test")
    with pytest.raises(RuntimeError, match="initialize"):
        await backend.upsert("id", [0.1], {})


async def test_not_initialized_raises_on_search():
    backend = PgvectorBackend("postgresql://test/test")
    with pytest.raises(RuntimeError, match="initialize"):
        await backend.search([0.1], 5, {})


async def test_not_initialized_raises_on_delete():
    backend = PgvectorBackend("postgresql://test/test")
    with pytest.raises(RuntimeError, match="initialize"):
        await backend.delete("id")


async def test_not_initialized_raises_on_delete_where():
    backend = PgvectorBackend("postgresql://test/test")
    with pytest.raises(RuntimeError, match="initialize"):
        await backend.delete_where({"scope_user_id": "alice"})


# ---------------------------------------------------------------------------
# ImportError guard
# ---------------------------------------------------------------------------


async def test_initialize_raises_import_error_without_asyncpg():
    import builtins

    real_import = builtins.__import__

    def mock_import(name, *args, **kwargs):
        if name in ("asyncpg", "pgvector", "pgvector.asyncpg"):
            raise ImportError("no module")
        return real_import(name, *args, **kwargs)

    backend = PgvectorBackend("postgresql://test/test")
    with patch("builtins.__import__", side_effect=mock_import):
        with pytest.raises(ImportError, match="railtracks\\[stores-vector\\]"):
            await backend.initialize()


# ---------------------------------------------------------------------------
# initialize
# ---------------------------------------------------------------------------


async def test_initialize_creates_extension_and_table():
    conn, pool = _make_pool()
    mock_asyncpg = MagicMock()
    mock_asyncpg.create_pool = AsyncMock(return_value=pool)
    mock_pgvector_asyncpg = MagicMock()
    mock_pgvector_asyncpg.register_vector = AsyncMock()

    with patch.dict(
        "sys.modules",
        {"asyncpg": mock_asyncpg, "pgvector.asyncpg": mock_pgvector_asyncpg},
    ):
        backend = PgvectorBackend("postgresql://test/test")
        await backend.initialize()

    executed_sql = [c.args[0] for c in conn.execute.call_args_list]
    assert any("CREATE EXTENSION" in s for s in executed_sql)
    assert any("CREATE TABLE" in s for s in executed_sql)
    assert backend._pool is pool


async def test_initialize_uses_dim_in_vector_type():
    conn, pool = _make_pool()
    mock_asyncpg = MagicMock()
    mock_asyncpg.create_pool = AsyncMock(return_value=pool)
    mock_pgvector_asyncpg = MagicMock()
    mock_pgvector_asyncpg.register_vector = AsyncMock()

    with patch.dict(
        "sys.modules",
        {"asyncpg": mock_asyncpg, "pgvector.asyncpg": mock_pgvector_asyncpg},
    ):
        backend = PgvectorBackend("postgresql://test/test", dim=1536)
        await backend.initialize()

    create_table_sql = next(
        c.args[0]
        for c in conn.execute.call_args_list
        if "CREATE TABLE" in c.args[0]
    )
    assert "vector(1536)" in create_table_sql


async def test_initialize_uses_untyped_vector_without_dim():
    conn, pool = _make_pool()
    mock_asyncpg = MagicMock()
    mock_asyncpg.create_pool = AsyncMock(return_value=pool)
    mock_pgvector_asyncpg = MagicMock()
    mock_pgvector_asyncpg.register_vector = AsyncMock()

    with patch.dict(
        "sys.modules",
        {"asyncpg": mock_asyncpg, "pgvector.asyncpg": mock_pgvector_asyncpg},
    ):
        backend = PgvectorBackend("postgresql://test/test")
        await backend.initialize()

    create_table_sql = next(
        c.args[0]
        for c in conn.execute.call_args_list
        if "CREATE TABLE" in c.args[0]
    )
    assert "vector(1536)" not in create_table_sql
    assert "vector" in create_table_sql


# ---------------------------------------------------------------------------
# upsert
# ---------------------------------------------------------------------------


async def test_upsert_passes_correct_args():
    conn, pool = _make_pool()
    backend = _injected_backend(pool)

    await backend.upsert("entry-1", [0.1, 0.2], {"scope_user_id": "alice"})

    conn.execute.assert_called_once()
    _, id_arg, vec_arg, payload_arg = conn.execute.call_args.args
    assert id_arg == "entry-1"
    assert vec_arg == [0.1, 0.2]
    assert json.loads(payload_arg) == {"scope_user_id": "alice"}


async def test_upsert_sql_contains_on_conflict():
    conn, pool = _make_pool()
    backend = _injected_backend(pool)

    await backend.upsert("e", [0.0], {})

    sql = conn.execute.call_args.args[0]
    assert "ON CONFLICT" in sql
    assert "DO UPDATE" in sql


# ---------------------------------------------------------------------------
# search
# ---------------------------------------------------------------------------


async def test_search_returns_empty_when_no_rows():
    conn, pool = _make_pool()
    conn.fetch.return_value = []
    backend = _injected_backend(pool)

    result = await backend.search([1.0, 0.0], 5, {})

    assert result == []


async def test_search_maps_rows_to_tuples():
    conn, pool = _make_pool()
    # Rows carry raw distance; score conversion happens in Python
    conn.fetch.return_value = [
        {"id": "a", "distance": 0.1, "payload": json.dumps({"k": "v1"})},
        {"id": "b", "distance": 0.3, "payload": json.dumps({"k": "v2"})},
    ]
    backend = _injected_backend(pool)

    results = await backend.search([1.0], 5, {})

    assert len(results) == 2
    assert results[0] == ("a", pytest.approx(0.9), {"k": "v1"})  # 1 - 0.1
    assert results[1] == ("b", pytest.approx(0.7), {"k": "v2"})  # 1 - 0.3


async def test_search_decodes_payload_dict_directly():
    """_decode_payload should handle dict payload (not just JSON strings)."""
    conn, pool = _make_pool()
    conn.fetch.return_value = [
        {"id": "a", "distance": 0.2, "payload": {"k": "v"}},
    ]
    backend = _injected_backend(pool)

    results = await backend.search([1.0], 5, {})

    assert results[0][2] == {"k": "v"}


async def test_search_passes_where_clause_for_filters():
    conn, pool = _make_pool()
    conn.fetch.return_value = []
    backend = _injected_backend(pool)

    await backend.search([1.0], 5, {"scope_user_id": "alice"})

    sql, vec_arg, key_arg, value_arg = conn.fetch.call_args.args
    assert "payload->$2::text = $3::jsonb" in sql
    assert "WHERE" in sql
    assert vec_arg == [1.0]
    assert key_arg == "scope_user_id"
    assert value_arg == json.dumps("alice")


async def test_search_no_where_clause_when_filters_empty():
    conn, pool = _make_pool()
    conn.fetch.return_value = []
    backend = _injected_backend(pool)

    await backend.search([1.0], 5, {})

    sql = conn.fetch.call_args.args[0]
    assert "WHERE" not in sql


async def test_search_sql_contains_cosine_operator():
    conn, pool = _make_pool()
    conn.fetch.return_value = []
    backend = _injected_backend(pool)  # default COSINE

    await backend.search([1.0], 5, {})

    sql = conn.fetch.call_args.args[0]
    assert "<=>" in sql


async def test_search_uses_l2_operator():
    conn, pool = _make_pool()
    conn.fetch.return_value = []
    backend = PgvectorBackend("postgresql://test/test", metric=DistanceMetric.L2)
    backend._pool = pool

    await backend.search([1.0], 5, {})

    sql = conn.fetch.call_args.args[0]
    assert "<->" in sql


async def test_search_uses_ip_operator():
    conn, pool = _make_pool()
    conn.fetch.return_value = []
    backend = PgvectorBackend("postgresql://test/test", metric=DistanceMetric.IP)
    backend._pool = pool

    await backend.search([1.0], 5, {})

    sql = conn.fetch.call_args.args[0]
    assert "<#>" in sql


def test_pg_to_score_cosine():
    assert _pg_to_score(DistanceMetric.COSINE, 0.1) == pytest.approx(0.9)
    assert _pg_to_score(DistanceMetric.COSINE, 0.0) == pytest.approx(1.0)


def test_pg_to_score_l2():
    assert _pg_to_score(DistanceMetric.L2, 0.0) == pytest.approx(1.0)
    assert _pg_to_score(DistanceMetric.L2, 1.0) == pytest.approx(0.5)
    assert _pg_to_score(DistanceMetric.L2, 3.0) == pytest.approx(0.25)


def test_pg_to_score_ip():
    # pgvector <#> returns -dot_product → score = -distance = dot_product
    assert _pg_to_score(DistanceMetric.IP, -0.8) == pytest.approx(0.8)
    assert _pg_to_score(DistanceMetric.IP, -0.3) == pytest.approx(0.3)


# ---------------------------------------------------------------------------
# delete
# ---------------------------------------------------------------------------


async def test_delete_passes_id():
    conn, pool = _make_pool()
    backend = _injected_backend(pool)

    await backend.delete("entry-1")

    sql, id_arg = conn.execute.call_args.args
    assert "DELETE" in sql
    assert id_arg == "entry-1"


# ---------------------------------------------------------------------------
# delete_where
# ---------------------------------------------------------------------------


async def test_delete_where_passes_where_clause():
    conn, pool = _make_pool()
    backend = _injected_backend(pool)

    await backend.delete_where({"scope_user_id": "alice"})

    sql, key_arg, value_arg = conn.execute.call_args.args
    assert "DELETE" in sql
    assert "payload->$1::text = $2::jsonb" in sql
    assert key_arg == "scope_user_id"
    assert value_arg == json.dumps("alice")


async def test_delete_where_empty_filters_is_noop():
    conn, pool = _make_pool()
    backend = _injected_backend(pool)

    await backend.delete_where({})

    conn.execute.assert_not_called()


# ---------------------------------------------------------------------------
# VectorStore integration (via mocked PgvectorBackend)
# ---------------------------------------------------------------------------


async def test_vector_store_write_read_via_pgvector():
    entry = _make_entry(vector=[1.0, 0.0, 0.0])

    from railtracks.retrieval.stores.vector.base import _entry_to_payload

    payload = _entry_to_payload(entry)

    conn, pool = _make_pool()
    conn.fetch.return_value = [
        {
            "id": str(entry.id),
            "distance": 0.05,  # cosine distance → score = 1 - 0.05 = 0.95
            "payload": json.dumps(payload),
        }
    ]

    store = VectorStore(_injected_backend(pool))
    write_id = await store.write(entry)
    assert write_id == str(entry.id)

    results = await store.read(
        StoreQuery(
            text="q",
            scope=StoreScope(user_id="alice"),
            embedding=[1.0, 0.0, 0.0],
            detail_level=DetailLevel.L2,
        )
    )

    assert len(results) == 1
    assert results[0].entry.id == entry.id
    assert results[0].score == pytest.approx(0.95)
    assert results[0].entry.content == "hello"
