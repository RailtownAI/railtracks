from __future__ import annotations

import asyncio
import re
from collections.abc import AsyncGenerator
from typing import TYPE_CHECKING, Any, Optional

from railtracks.retrieval.loaders.base import BaseDocumentLoader
from railtracks.retrieval.models import Document, DocumentType

if TYPE_CHECKING:
    from sqlalchemy import Engine

_IDENT_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_$]*(\.[A-Za-z_][A-Za-z0-9_$]*)?$")


def _looks_like_query(s: str) -> bool:
    """Return True if *s* appears to be a raw SQL statement rather than a table name."""
    return s.strip().upper().startswith("SELECT")


def _validate_identifier(value: str, label: str) -> None:
    """Raise ValueError if *value* is not a safe SQL identifier."""
    if not _IDENT_RE.match(value):
        raise ValueError(
            f"Invalid SQL identifier for {label!r}: {value!r}. "
            "Identifiers must start with a letter or underscore and may only "
            "contain letters, digits, underscores, and dollar signs. "
            "Use 'schema.table' notation for schema-qualified names. "
            "Never pass user-controlled strings as identifiers."
        )


class SQLLoader(BaseDocumentLoader):
    """Document loader for relational databases via SQLAlchemy.

    Reads rows from a table (or arbitrary ``SELECT`` query) and converts each
    row into a :class:`Document`.

    Works with any SQLAlchemy-compatible database including PostgreSQL,
    Supabase (PostgreSQL), MySQL, SQLite, and more. For SQLite no extra
    driver is needed; for PostgreSQL install ``psycopg2`` or ``asyncpg``.

    Requires the ``sql`` extra: ``pip install railtracks[sql]``.

    Args:
        connection_string: SQLAlchemy database URL.
        table_or_query: Either a **table name** or a full ``SELECT`` statement.
            Table names produce ``SELECT * FROM <table>``.

            .. note::
               Table names are validated against a strict allowlist
               (``[A-Za-z_][A-Za-z0-9_$]*``) at construction time. Never
               pass user-controlled strings here.

        content_column: Name of the column whose value becomes
            :attr:`Document.content`.
        keys: Explicit list of ``id_column`` values to load. When set,
            ``id_column`` must also be provided. When ``None`` (default), all
            rows are loaded.
        metadata_columns: Column names to include in :attr:`Document.metadata`.
            When ``None`` all columns except ``content_column`` and
            ``id_column`` are included.
        id_column: Column whose value is preserved in :attr:`Document.source`
            (when ``source_column`` is not set) and used as the lookup key for
            ``keys`` filtering. :attr:`Document.id` is always an auto-generated
            UUID regardless of this value.
        source_column: Column to use as :attr:`Document.source`. Falls back
            to ``id_column`` when ``None``.
        engine: An existing ``sqlalchemy.Engine`` instance.
        engine_kwargs: Extra keyword arguments forwarded to
            ``sqlalchemy.create_engine()``.

    Raises:
        ImportError: If ``sqlalchemy`` is not installed.
        ValueError: If an identifier argument contains unsafe characters, or
            if ``keys`` is provided without an ``id_column``.
    """

    def __init__(
        self,
        connection_string: str,
        table_or_query: str,
        content_column: str,
        *,
        keys: Optional[list[str]] = None,
        metadata_columns: Optional[list[str]] = None,
        id_column: Optional[str] = None,
        source_column: Optional[str] = None,
        engine: Optional[Engine] = None,
        engine_kwargs: Optional[dict[str, Any]] = None,
    ) -> None:
        try:
            import sqlalchemy  # noqa: F401
        except ImportError:
            raise ImportError(
                "sqlalchemy is required for SQL loading. "
                "Install it via `pip install railtracks[sql]` or `uv add railtracks[sql]`."
            )

        import sqlalchemy as sa

        self._content_column = content_column
        self._metadata_columns = metadata_columns
        self._id_column = id_column
        self._source_column = source_column
        self._table_or_query = table_or_query
        self._is_raw_query = _looks_like_query(table_or_query)
        self._keys = list(keys) if keys is not None else None

        if self._keys is not None and id_column is None:
            raise ValueError(
                "An 'id_column' must be set when filtering by 'keys'."
            )

        if not self._is_raw_query:
            _validate_identifier(table_or_query, "table_or_query")
        _validate_identifier(content_column, "content_column")
        if id_column is not None:
            _validate_identifier(id_column, "id_column")
        if source_column is not None:
            _validate_identifier(source_column, "source_column")
        if metadata_columns is not None:
            for col in metadata_columns:
                _validate_identifier(col, f"metadata_columns[{col!r}]")

        self._owns_engine = engine is None
        if engine is not None:
            self._engine = engine
        else:
            self._engine = sa.create_engine(
                connection_string,
                **(engine_kwargs or {}),
            )

    def __repr__(self) -> str:
        url = self._engine.url.render_as_string(hide_password=True)
        return f"SQLLoader(url={url!r}, table_or_query={self._table_or_query!r})"

    def close(self) -> None:
        """Dispose the underlying SQLAlchemy engine.

        Only disposes engines created internally by this loader.
        """
        if self._owns_engine:
            self._engine.dispose()

    def __enter__(self) -> SQLLoader:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def _row_to_document(self, row: dict[str, Any]) -> Document:
        if self._content_column not in row:
            available = sorted(row.keys())
            raise ValueError(
                f"content_column {self._content_column!r} was not found in the "
                f"query results. Available columns: {available}. "
                "Check that 'content_column' matches a column returned by the query."
            )
        content = str(row[self._content_column])

        if self._metadata_columns is not None:
            meta = {col: row[col] for col in self._metadata_columns if col in row}
        else:
            excluded = {self._content_column}
            if self._id_column:
                excluded.add(self._id_column)
            meta = {k: v for k, v in row.items() if k not in excluded}

        # Document.id is always an auto-generated UUID. The row's id_column
        # value (typically not a UUID for relational data) is preserved in
        # Document.source so it can round-trip back into the database.
        source_col = self._source_column or self._id_column
        if source_col and source_col in row and row[source_col] is not None:
            source = str(row[source_col])
        else:
            source = self._table_or_query

        return Document(
            content=content,
            type=DocumentType.TEXT,
            source=source,
            metadata=meta,
        )

    def _fetch_all(self) -> list[dict[str, Any]]:
        import sqlalchemy as sa

        if self._is_raw_query:
            stmt = sa.text(self._table_or_query)
        else:
            stmt = sa.text(f"SELECT * FROM {self._table_or_query}")  # noqa: S608

        with self._engine.connect() as conn:
            result = conn.execute(stmt)
            return [dict(row._mapping) for row in result]

    def _fetch_by_ids(self, keys: list[str]) -> list[dict[str, Any]]:
        import sqlalchemy as sa

        if self._is_raw_query:
            base = self._table_or_query.rstrip(";")
            stmt = sa.text(
                f"SELECT * FROM ({base}) AS _sub "  # noqa: S608
                f"WHERE {self._id_column} IN :keys"
            ).bindparams(sa.bindparam("keys", expanding=True))
        else:
            stmt = sa.text(
                f"SELECT * FROM {self._table_or_query} "  # noqa: S608
                f"WHERE {self._id_column} IN :keys"
            ).bindparams(sa.bindparam("keys", expanding=True))

        with self._engine.connect() as conn:
            result = conn.execute(stmt, {"keys": keys})
            return [dict(row._mapping) for row in result]

    def _fetch_rows(self) -> list[dict[str, Any]]:
        if self._keys is not None:
            if not self._keys:
                return []
            return self._fetch_by_ids(self._keys)
        return self._fetch_all()

    async def astream(self) -> AsyncGenerator[Document, None]:
        """Stream documents one at a time as rows are read.

        Yields:
            Document: The next row as a document.
        """
        rows = await asyncio.to_thread(self._fetch_rows)
        for row in rows:
            yield self._row_to_document(row)
