"""Unit tests for SQLLoader (real in-memory SQLite)."""

from __future__ import annotations

import sys

import pytest
from railtracks.retrieval.models import Document, DocumentType

from .conftest import make_sqlite_engine

ROWS = [
    {"id": "doc-1", "title": "First Doc", "body": "Content of first document."},
    {"id": "doc-2", "title": "Second Doc", "body": "Content of second document."},
    {"id": "doc-3", "title": "Third Doc", "body": "Content of third document."},
]


# ---------------------------------------------------------------------------
# SQLLoader
# ---------------------------------------------------------------------------


@pytest.fixture()
def populated_engine():
    """SQLite engine pre-populated with three rows in the 'documents' table."""
    return make_sqlite_engine(ROWS, table="documents")


@pytest.fixture()
def loader(populated_engine):
    from railtracks.retrieval.loaders.cloud.sql import SQLLoader

    return SQLLoader(
        "",
        table_or_query="documents",
        content_columns="body",
        id_column="id",
        source_column="title",
        metadata_columns=["title"],
        engine=populated_engine,
    )


class TestSQLLoaderInit:
    def test_raises_import_error_when_sqlalchemy_missing(self) -> None:
        original = sys.modules.pop("sqlalchemy", None)
        try:
            from unittest.mock import patch

            with patch.dict(sys.modules, {"sqlalchemy": None}):
                from railtracks.retrieval.loaders.cloud.sql import SQLLoader

                with pytest.raises(ImportError, match="sqlalchemy"):
                    SQLLoader("sqlite:///:memory:", "docs", "body")
        finally:
            if original is not None:
                sys.modules["sqlalchemy"] = original

    def test_import_error_mentions_extra(self) -> None:
        from unittest.mock import patch

        with patch.dict(sys.modules, {"sqlalchemy": None}):
            from railtracks.retrieval.loaders.cloud.sql import SQLLoader

            with pytest.raises(ImportError, match="railtracks\\[sql\\]"):
                SQLLoader("sqlite:///:memory:", "docs", "body")

    def test_keys_without_id_column_raises(self, populated_engine) -> None:
        from railtracks.retrieval.loaders.cloud.sql import SQLLoader

        with pytest.raises(ValueError, match="id_column"):
            SQLLoader(
                "",
                "documents",
                "body",
                ids=["doc-1"],
                engine=populated_engine,
            )


class TestSQLLoaderLoad:
    def test_returns_all_rows(self, loader) -> None:
        docs = loader.load()
        assert len(docs) == 3

    def test_documents_are_document_instances(self, loader) -> None:
        assert all(isinstance(d, Document) for d in loader.load())

    def test_content_column_maps_to_document_content(self, loader) -> None:
        contents = {d.content for d in loader.load()}
        assert contents == {r["body"] for r in ROWS}

    def test_source_column_maps_to_document_source(self, loader) -> None:
        sources = {d.source for d in loader.load()}
        assert sources == {"First Doc", "Second Doc", "Third Doc"}

    def test_document_type_is_text(self, loader) -> None:
        for doc in loader.load():
            assert doc.type == DocumentType.TEXT

    def test_metadata_columns_included(self, loader) -> None:
        for doc in loader.load():
            assert "title" in doc.metadata

    def test_content_column_excluded_from_metadata(self, loader) -> None:
        for doc in loader.load():
            assert "body" not in doc.metadata

    def test_empty_table_returns_empty_list(self, populated_engine) -> None:
        import sqlalchemy as sa
        from railtracks.retrieval.loaders.cloud.sql import SQLLoader

        with populated_engine.begin() as conn:
            conn.execute(sa.text("DELETE FROM documents"))
        loader = SQLLoader("", "documents", "body", engine=populated_engine)
        assert loader.load() == []


class TestSQLLoaderRawQuery:
    def test_raw_select_returns_correct_rows(self, populated_engine) -> None:
        from railtracks.retrieval.loaders.cloud.sql import SQLLoader

        loader = SQLLoader(
            "",
            table_or_query="SELECT id, body FROM documents WHERE id = 'doc-1'",
            content_columns="body",
            id_column="id",
            engine=populated_engine,
        )
        docs = loader.load()
        assert len(docs) == 1
        assert docs[0].content == "Content of first document."

    def test_raw_query_detected_case_insensitive(self, populated_engine) -> None:
        from railtracks.retrieval.loaders.cloud.sql import SQLLoader

        loader = SQLLoader(
            "",
            table_or_query="select id, body from documents",
            content_columns="body",
            engine=populated_engine,
        )
        docs = loader.load()
        assert len(docs) == 3


class TestSQLLoaderKeysFilter:
    def test_only_requested_rows_loaded(self, populated_engine) -> None:
        from railtracks.retrieval.loaders.cloud.sql import SQLLoader

        loader = SQLLoader(
            "",
            "documents",
            "body",
            id_column="id",
            ids=["doc-1", "doc-3"],
            engine=populated_engine,
        )
        docs = loader.load()
        assert len(docs) == 2

    def test_empty_keys_returns_empty_list(self, populated_engine) -> None:
        from railtracks.retrieval.loaders.cloud.sql import SQLLoader

        loader = SQLLoader(
            "",
            "documents",
            "body",
            id_column="id",
            ids=[],
            engine=populated_engine,
        )
        assert loader.load() == []

    def test_unknown_key_returns_empty_list(self, populated_engine) -> None:
        from railtracks.retrieval.loaders.cloud.sql import SQLLoader

        loader = SQLLoader(
            "",
            "documents",
            "body",
            id_column="id",
            ids=["does-not-exist"],
            engine=populated_engine,
        )
        assert loader.load() == []


class TestSQLLoaderAutoMetadata:
    def test_all_non_content_columns_in_metadata(self, populated_engine) -> None:
        from railtracks.retrieval.loaders.cloud.sql import SQLLoader

        loader = SQLLoader(
            "",
            "documents",
            content_columns="body",
            id_column="id",
            engine=populated_engine,
        )
        for doc in loader.load():
            assert "body" not in doc.metadata
            assert "id" not in doc.metadata
            assert "title" in doc.metadata


@pytest.mark.asyncio
class TestSQLLoaderAsync:
    async def test_aload_returns_all_rows(self, loader) -> None:
        docs = await loader.aload()
        assert len(docs) == 3
        assert {d.content for d in docs} == {r["body"] for r in ROWS}


class TestSQLLoaderContentColumns:
    def test_multiple_columns_joined_with_separator(self, populated_engine) -> None:
        from railtracks.retrieval.loaders.cloud.sql import SQLLoader

        loader = SQLLoader(
            "",
            "documents",
            ["title", "body"],
            content_separator=" | ",
            engine=populated_engine,
        )
        contents = {d.content for d in loader.load()}
        assert contents == {f"{r['title']} | {r['body']}" for r in ROWS}

    def test_default_separator_is_newline(self, populated_engine) -> None:
        from railtracks.retrieval.loaders.cloud.sql import SQLLoader

        loader = SQLLoader("", "documents", ["title", "body"], engine=populated_engine)
        contents = {d.content for d in loader.load()}
        assert contents == {f"{r['title']}\n{r['body']}" for r in ROWS}

    def test_all_content_columns_excluded_from_metadata(self, populated_engine) -> None:
        from railtracks.retrieval.loaders.cloud.sql import SQLLoader

        loader = SQLLoader("", "documents", ["title", "body"], engine=populated_engine)
        for doc in loader.load():
            assert "title" not in doc.metadata
            assert "body" not in doc.metadata

    def test_each_content_column_is_validated(self, populated_engine) -> None:
        from railtracks.retrieval.loaders.cloud.sql import SQLLoader

        with pytest.raises(ValueError, match="Invalid SQL identifier"):
            SQLLoader("", "documents", ["body", "x; DROP"], engine=populated_engine)

    def test_missing_content_columns_raises_type_error(self, populated_engine) -> None:
        from railtracks.retrieval.loaders.cloud.sql import SQLLoader

        with pytest.raises(TypeError, match="content_columns"):
            SQLLoader("", "documents", engine=populated_engine)


class TestSQLLoaderRenamedArguments:
    def test_content_column_keyword_warns(self, populated_engine) -> None:
        from railtracks.retrieval.loaders.cloud.sql import SQLLoader

        with pytest.warns(
            FutureWarning, match=r"SQLLoader\(content_column=.*2\.0\.0"
        ) as rec:
            loader = SQLLoader(
                "", "documents", content_column="body", engine=populated_engine
            )
        assert "content_columns=" in str(rec[0].message)
        assert rec[0].filename == __file__
        assert {d.content for d in loader.load()} == {r["body"] for r in ROWS}

    def test_keys_keyword_warns(self, populated_engine) -> None:
        from railtracks.retrieval.loaders.cloud.sql import SQLLoader

        with pytest.warns(FutureWarning, match=r"SQLLoader\(keys=.*2\.0\.0") as rec:
            loader = SQLLoader(
                "",
                "documents",
                "body",
                id_column="id",
                keys=["doc-1"],
                engine=populated_engine,
            )
        assert "ids=" in str(rec[0].message)
        assert len(loader.load()) == 1

    def test_positional_content_column_is_silent(
        self, populated_engine, recwarn
    ) -> None:
        from railtracks.retrieval.loaders.cloud.sql import SQLLoader

        SQLLoader("", "documents", "body", engine=populated_engine)
        assert not [w for w in recwarn if issubclass(w.category, FutureWarning)]

    @pytest.mark.parametrize(
        ("old", "new", "value"),
        [("content_column", "content_columns", "body"), ("keys", "ids", ["doc-1"])],
    )
    def test_passing_both_names_raises(self, populated_engine, old, new, value) -> None:
        from railtracks.retrieval.loaders.cloud.sql import SQLLoader

        kwargs = {"content_columns": "body", "id_column": "id", old: value, new: value}
        with pytest.raises(TypeError, match=rf"{old}.*{new}"):
            SQLLoader("", "documents", engine=populated_engine, **kwargs)
