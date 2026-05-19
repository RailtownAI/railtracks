"""Unit tests for SQLWriter (real in-memory SQLite — no mocking needed)."""

import pytest

from railtracks.vector_stores.chunking.base_chunker import Chunk

from .conftest import make_sqlite_engine, read_all_rows


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_chunk(id_=None, document=None, content="hello", metadata=None):
    return Chunk(
        content=content,
        id=id_,
        document=document,
        metadata=metadata or {},
    )


# ---------------------------------------------------------------------------
# Init
# ---------------------------------------------------------------------------


class TestInit:
    def test_missing_sqlalchemy_raises(self, monkeypatch):
        import sys

        monkeypatch.setitem(sys.modules, "sqlalchemy", None)
        with pytest.raises(ImportError, match="sqlalchemy"):
            from railtracks.writers.sql import SQLWriter

            SQLWriter("", "docs", "body")


# ---------------------------------------------------------------------------
# write_key
# ---------------------------------------------------------------------------


class TestWriteKey:
    def test_inserts_row(self):
        engine = make_sqlite_engine(columns=["id", "body"])
        from railtracks.writers.sql import SQLWriter

        writer = SQLWriter("", "documents", "body", id_column="id", engine=engine)
        uri = writer.write_key("doc-1", "some content")

        rows = read_all_rows(engine)
        assert len(rows) == 1
        assert rows[0]["id"] == "doc-1"
        assert rows[0]["body"] == "some content"
        assert uri == "sql://documents/doc-1"

    def test_write_key_without_id_column_raises(self):
        engine = make_sqlite_engine(columns=["body"])
        from railtracks.writers.sql import SQLWriter

        writer = SQLWriter("", "documents", "body", engine=engine)
        with pytest.raises(ValueError, match="id_column"):
            writer.write_key("k", "content")

    def test_upsert_replaces_existing_row(self):
        engine = make_sqlite_engine(columns=["id", "body"])
        from railtracks.writers.sql import SQLWriter

        writer = SQLWriter("", "documents", "body", id_column="id", engine=engine)
        writer.write_key("doc-1", "first version")
        writer.write_key("doc-1", "second version")

        rows = read_all_rows(engine)
        assert len(rows) == 1
        assert rows[0]["body"] == "second version"

    def test_insert_mode_allows_duplicate_ids(self):
        engine = make_sqlite_engine(columns=["id", "body"])
        from railtracks.writers.sql import SQLWriter

        writer = SQLWriter(
            "", "documents", "body", id_column="id", mode="insert", engine=engine
        )
        writer.write_key("doc-1", "v1")
        writer.write_key("doc-1", "v2")

        rows = read_all_rows(engine)
        assert len(rows) == 2


# ---------------------------------------------------------------------------
# write
# ---------------------------------------------------------------------------


class TestWrite:
    def test_inserts_all_chunks(self):
        engine = make_sqlite_engine(columns=["id", "body"])
        from railtracks.writers.sql import SQLWriter

        chunks = [make_chunk(id_=f"doc-{i}", content=f"content {i}") for i in range(3)]
        writer = SQLWriter("", "documents", "body", id_column="id", engine=engine)
        uris = writer.write(chunks)

        rows = read_all_rows(engine)
        assert len(rows) == 3
        assert len(uris) == 3

    def test_content_column_written(self):
        engine = make_sqlite_engine(columns=["id", "body"])
        from railtracks.writers.sql import SQLWriter

        chunk = make_chunk(id_="x", content="the quick brown fox")
        writer = SQLWriter("", "documents", "body", id_column="id", engine=engine)
        writer.write([chunk])

        rows = read_all_rows(engine)
        assert rows[0]["body"] == "the quick brown fox"

    def test_id_column_written(self):
        engine = make_sqlite_engine(columns=["id", "body"])
        from railtracks.writers.sql import SQLWriter

        chunk = make_chunk(id_="my-id", content="x")
        writer = SQLWriter("", "documents", "body", id_column="id", engine=engine)
        writer.write([chunk])

        rows = read_all_rows(engine)
        assert rows[0]["id"] == "my-id"

    def test_document_column_written(self):
        engine = make_sqlite_engine(columns=["id", "title", "body"])
        from railtracks.writers.sql import SQLWriter

        chunk = make_chunk(id_="1", document="My Title", content="body text")
        writer = SQLWriter(
            "",
            "documents",
            "body",
            id_column="id",
            document_column="title",
            engine=engine,
        )
        writer.write([chunk])

        rows = read_all_rows(engine)
        assert rows[0]["title"] == "My Title"

    def test_metadata_columns_written(self):
        engine = make_sqlite_engine(columns=["id", "body", "category"])
        from railtracks.writers.sql import SQLWriter

        chunk = make_chunk(
            id_="1",
            content="body",
            metadata={"category": "HR", "ignored": "value"},
        )
        writer = SQLWriter(
            "",
            "documents",
            "body",
            id_column="id",
            metadata_columns=["category"],
            engine=engine,
        )
        writer.write([chunk])

        rows = read_all_rows(engine)
        assert rows[0]["category"] == "HR"

    def test_missing_metadata_key_skipped(self):
        engine = make_sqlite_engine(columns=["id", "body", "category"])
        from railtracks.writers.sql import SQLWriter

        chunk = make_chunk(id_="1", content="body", metadata={})
        writer = SQLWriter(
            "",
            "documents",
            "body",
            id_column="id",
            metadata_columns=["category"],
            engine=engine,
        )
        # Should not raise even when the metadata key is absent
        writer.write([chunk])

        rows = read_all_rows(engine)
        assert rows[0]["category"] is None

    def test_upsert_mode_replaces_row(self):
        engine = make_sqlite_engine(columns=["id", "body"])
        from railtracks.writers.sql import SQLWriter

        writer = SQLWriter("", "documents", "body", id_column="id", engine=engine)
        writer.write([make_chunk(id_="doc-1", content="v1")])
        writer.write([make_chunk(id_="doc-1", content="v2")])

        rows = read_all_rows(engine)
        assert len(rows) == 1
        assert rows[0]["body"] == "v2"

    def test_insert_mode_appends(self):
        engine = make_sqlite_engine(columns=["id", "body"])
        from railtracks.writers.sql import SQLWriter

        writer = SQLWriter(
            "", "documents", "body", id_column="id", mode="insert", engine=engine
        )
        writer.write([make_chunk(id_="doc-1", content="v1")])
        writer.write([make_chunk(id_="doc-1", content="v2")])

        rows = read_all_rows(engine)
        assert len(rows) == 2

    def test_returns_uri_with_id(self):
        engine = make_sqlite_engine(columns=["id", "body"])
        from railtracks.writers.sql import SQLWriter

        chunk = make_chunk(id_="abc", content="x")
        writer = SQLWriter("", "documents", "body", id_column="id", engine=engine)
        uris = writer.write([chunk])

        assert uris == ["sql://documents/abc"]

    def test_returns_uri_without_id(self):
        engine = make_sqlite_engine(columns=["body"])
        from railtracks.writers.sql import SQLWriter

        chunk = make_chunk(content="x")
        writer = SQLWriter("", "documents", "body", engine=engine)
        uris = writer.write([chunk])

        assert uris == ["sql://documents"]

    def test_empty_chunks(self):
        engine = make_sqlite_engine(columns=["id", "body"])
        from railtracks.writers.sql import SQLWriter

        writer = SQLWriter("", "documents", "body", id_column="id", engine=engine)
        uris = writer.write([])

        assert uris == []
        assert read_all_rows(engine) == []

    def test_chunk_auto_uuid_written_to_id_column(self):
        engine = make_sqlite_engine(columns=["id", "body"])
        from railtracks.writers.sql import SQLWriter

        # Chunk always auto-assigns a UUID in __post_init__, so id_column
        # always receives the auto-generated UUID when id_column is configured.
        chunk = make_chunk(id_=None, content="x")
        writer = SQLWriter("", "documents", "body", id_column="id", engine=engine)
        writer.write([chunk])

        rows = read_all_rows(engine)
        assert rows[0]["body"] == "x"
        assert rows[0]["id"] is not None
        assert len(rows[0]["id"]) == 36  # UUID4


# ---------------------------------------------------------------------------
# Async
# ---------------------------------------------------------------------------


class TestAsync:
    @pytest.mark.asyncio
    async def test_awrite(self):
        engine = make_sqlite_engine(columns=["id", "body"])
        from railtracks.writers.sql import SQLWriter

        chunks = [make_chunk(id_="x", content="async content")]
        writer = SQLWriter("", "documents", "body", id_column="id", engine=engine)
        uris = await writer.awrite(chunks)

        assert uris == ["sql://documents/x"]
        rows = read_all_rows(engine)
        assert rows[0]["body"] == "async content"

    @pytest.mark.asyncio
    async def test_awrite_key(self):
        engine = make_sqlite_engine(columns=["id", "body"])
        from railtracks.writers.sql import SQLWriter

        writer = SQLWriter("", "documents", "body", id_column="id", engine=engine)
        uri = await writer.awrite_key("k", "data")

        assert uri == "sql://documents/k"
        rows = read_all_rows(engine)
        assert rows[0]["id"] == "k"
        assert rows[0]["body"] == "data"
