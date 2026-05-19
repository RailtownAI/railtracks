"""
SQLLoader tests use a real in-memory SQLite database (no mocking).
SQLite is part of Python's stdlib so these tests run with zero extra
cloud credentials or installed services.
"""

import sys

import pytest

from railtracks.loaders.sql import SQLLoader
from railtracks.vector_stores.chunking.base_chunker import Chunk

from .conftest import make_sqlite_engine

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

ROWS = [
    {"id": "doc-1", "title": "First Doc",  "body": "Content of first document."},
    {"id": "doc-2", "title": "Second Doc", "body": "Content of second document."},
    {"id": "doc-3", "title": "Third Doc",  "body": "Content of third document."},
]


@pytest.fixture()
def sqlite_engine():
    """Spin up an in-memory SQLite engine pre-populated with three rows.

    We pass the engine object directly into SQLLoader (via the `engine`
    kwarg) so that both share the same in-memory connection pool — SQLite
    in-memory databases are connection-scoped and would be empty if SQLLoader
    opened a new connection via a URL.
    """
    return make_sqlite_engine(ROWS, table="documents")


@pytest.fixture()
def loader(sqlite_engine) -> SQLLoader:
    return SQLLoader(
        "",  # unused when engine= is provided
        table_or_query="documents",
        content_column="body",
        id_column="id",
        document_column="title",
        metadata_columns=["title"],
        engine=sqlite_engine,
    )


# ---------------------------------------------------------------------------
# Init
# ---------------------------------------------------------------------------


class TestSQLLoaderInit:
    def test_raises_import_error_when_sqlalchemy_missing(self) -> None:
        with pytest.raises(ImportError, match="sqlalchemy"):
            # Patch sqlalchemy out of the import system then force a re-init
            original = sys.modules.pop("sqlalchemy", None)
            try:
                from unittest.mock import patch
                with patch.dict(sys.modules, {"sqlalchemy": None}):
                    SQLLoader("sqlite:///:memory:", "docs", "body")
            finally:
                if original is not None:
                    sys.modules["sqlalchemy"] = original

    def test_import_error_message_mentions_extra(self) -> None:
        from unittest.mock import patch
        with patch.dict(sys.modules, {"sqlalchemy": None}):
            with pytest.raises(ImportError, match="railtracks\\[sql\\]"):
                SQLLoader("sqlite:///:memory:", "docs", "body")


# ---------------------------------------------------------------------------
# load() — table name
# ---------------------------------------------------------------------------


class TestSQLLoaderLoad:
    def test_returns_all_rows(self, loader: SQLLoader) -> None:
        chunks = loader.load()
        assert len(chunks) == 3

    def test_all_chunks_are_chunk_instances(self, loader: SQLLoader) -> None:
        assert all(isinstance(c, Chunk) for c in loader.load())

    def test_content_column_maps_to_chunk_content(self, loader: SQLLoader) -> None:
        contents = {c.content for c in loader.load()}
        assert contents == {r["body"] for r in ROWS}

    def test_id_column_maps_to_chunk_id(self, loader: SQLLoader) -> None:
        ids = {c.id for c in loader.load()}
        assert ids == {"doc-1", "doc-2", "doc-3"}

    def test_document_column_maps_to_chunk_document(self, loader: SQLLoader) -> None:
        docs = {c.document for c in loader.load()}
        assert docs == {"First Doc", "Second Doc", "Third Doc"}

    def test_metadata_contains_source(self, loader: SQLLoader) -> None:
        for chunk in loader.load():
            assert "source" in chunk.metadata

    def test_metadata_columns_included(self, loader: SQLLoader) -> None:
        for chunk in loader.load():
            assert "title" in chunk.metadata

    def test_content_column_excluded_from_metadata(self, loader: SQLLoader) -> None:
        for chunk in loader.load():
            assert "body" not in chunk.metadata

    def test_empty_table_returns_empty_list(self, sqlite_engine) -> None:
        import sqlalchemy as sa
        with sqlite_engine.begin() as conn:
            conn.execute(sa.text("DELETE FROM documents"))
        loader = SQLLoader("", "documents", "body", engine=sqlite_engine)
        assert loader.load() == []

    def test_prefix_argument_is_ignored(self, loader: SQLLoader) -> None:
        all_chunks = loader.load()
        prefixed_chunks = loader.load(prefix="anything")
        assert len(all_chunks) == len(prefixed_chunks)


# ---------------------------------------------------------------------------
# load() — raw SQL query
# ---------------------------------------------------------------------------


class TestSQLLoaderRawQuery:
    def test_raw_select_returns_correct_rows(self, sqlite_engine) -> None:
        loader = SQLLoader(
            "",
            table_or_query="SELECT id, body FROM documents WHERE id = 'doc-1'",
            content_column="body",
            id_column="id",
            engine=sqlite_engine,
        )
        chunks = loader.load()
        assert len(chunks) == 1
        assert chunks[0].content == "Content of first document."

    def test_raw_query_detected_case_insensitive(self, sqlite_engine) -> None:
        loader = SQLLoader(
            "",
            table_or_query="select id, body from documents",
            content_column="body",
            engine=sqlite_engine,
        )
        chunks = loader.load()
        assert len(chunks) == 3


# ---------------------------------------------------------------------------
# load_keys()
# ---------------------------------------------------------------------------


class TestSQLLoaderLoadKeys:
    def test_returns_only_requested_rows(self, loader: SQLLoader) -> None:
        chunks = loader.load_keys(["doc-1", "doc-3"])
        assert len(chunks) == 2
        ids = {c.id for c in chunks}
        assert ids == {"doc-1", "doc-3"}

    def test_empty_keys_returns_empty_list(self, loader: SQLLoader) -> None:
        assert loader.load_keys([]) == []

    def test_raises_without_id_column(self, sqlite_engine) -> None:
        loader_no_id = SQLLoader("", "documents", "body", engine=sqlite_engine)
        with pytest.raises(ValueError, match="id_column"):
            loader_no_id.load_keys(["doc-1"])

    def test_unknown_key_returns_empty_list(self, loader: SQLLoader) -> None:
        chunks = loader.load_keys(["does-not-exist"])
        assert chunks == []


# ---------------------------------------------------------------------------
# Auto metadata — no metadata_columns specified
# ---------------------------------------------------------------------------


class TestSQLLoaderAutoMetadata:
    def test_all_non_content_columns_in_metadata(self, sqlite_engine) -> None:
        loader = SQLLoader(
            "",
            "documents",
            content_column="body",
            id_column="id",
            engine=sqlite_engine,
        )
        for chunk in loader.load():
            # id excluded because it's id_column; body excluded because content_column
            assert "body" not in chunk.metadata
            assert "id" not in chunk.metadata
            assert "title" in chunk.metadata


# ---------------------------------------------------------------------------
# Async
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestSQLLoaderAsync:
    async def test_aload_matches_sync_load(self, loader: SQLLoader) -> None:
        sync = loader.load()
        async_ = await loader.aload()
        assert len(async_) == len(sync)
        assert {c.content for c in async_} == {c.content for c in sync}

    async def test_aload_keys_matches_sync_load_keys(self, loader: SQLLoader) -> None:
        sync = loader.load_keys(["doc-2"])
        async_ = await loader.aload_keys(["doc-2"])
        assert len(async_) == len(sync)
        assert async_[0].content == sync[0].content
