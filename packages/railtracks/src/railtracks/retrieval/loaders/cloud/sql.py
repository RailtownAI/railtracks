from __future__ import annotations

import asyncio
import re
import warnings
from collections.abc import AsyncGenerator
from typing import TYPE_CHECKING, Any, Optional

from railtracks.retrieval.content_extraction import labelled_join
from railtracks.retrieval.loaders.base import (
    RENAMED_ARGUMENTS_GUIDE,
    BaseDocumentLoader,
)
from railtracks.retrieval.models import Document, DocumentType
from railtracks.utils.deprecation import renamed_kwargs

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

        content_columns: Column, or list of columns, whose values become
            :attr:`Document.content`. A single column name gives that column's
            value as-is; a list gives ``"col: value"`` lines joined with
            ``content_separator``, as in :class:`CSVLoader`.
        ids: Explicit list of ``id_column`` values to load. When set,
            ``id_column`` must also be provided. When ``None`` (default), all
            rows are loaded.
        metadata_columns: Column names to include in :attr:`Document.metadata`.
            When ``None`` all columns except ``content_columns`` and
            ``id_column`` are included.
        id_column: Column whose value is used (namespaced by
            ``table_or_query``) to build :attr:`Document.source` when
            ``source_column`` is not set, and as the lookup key for ``ids``
            filtering. :attr:`Document.id` is derived from ``source`` via
            ``uuid5``, so the namespaced form must be unique per row.
        source_column: Column whose value is used (namespaced by
            ``table_or_query``) as :attr:`Document.source`. Falls back to
            ``id_column``, then to ``row={N}`` (0-based row index), when
            unset/missing/NULL. The ``row=`` prefix keeps index fallbacks
            out of the same namespace as real column values.

            For a raw ``SELECT``, the source includes the full query text, so
            editing the query gives every row a new id, and copies stored
            under the old ids stay in the store.

            Without an ``id_column`` or ``source_column``, ids follow row
            order, and ``SELECT * FROM table`` does not guarantee an order.
            One reordered row shifts every row after it, so they are all
            re-embedded. Set ``id_column`` or add an ``ORDER BY`` to avoid
            that.
        content_separator: String used to join the content-column lines.
            Defaults to ``"\\n"``.
        engine: An existing ``sqlalchemy.Engine`` instance.
        engine_kwargs: Extra keyword arguments forwarded to
            ``sqlalchemy.create_engine()``.

    Raises:
        ImportError: If ``sqlalchemy`` is not installed.
        TypeError: If ``content_column`` or ``keys``, the deprecated names for
            ``content_columns`` and ``ids`` (removed in 2.0.0), is passed
            together with its replacement.
        ValueError: If ``content_columns`` is empty, an identifier argument
            contains unsafe characters, or ``ids`` is provided without an
            ``id_column``.
    """

    @renamed_kwargs(
        content_column="content_columns",
        keys="ids",
        version="2.0.0",
        guide=RENAMED_ARGUMENTS_GUIDE,
    )
    def __init__(
        self,
        connection_string: str,
        table_or_query: str,
        content_columns: str | list[str],
        *,
        ids: Optional[list[str]] = None,
        metadata_columns: Optional[list[str]] = None,
        id_column: Optional[str] = None,
        source_column: Optional[str] = None,
        content_separator: str = "\n",
        engine: Optional[Engine] = None,
        engine_kwargs: Optional[dict[str, Any]] = None,
    ) -> None:
        try:
            import sqlalchemy as sa  # noqa: F401
        except ImportError:
            raise ImportError(
                "sqlalchemy is required for SQL loading. "
                "Install it via `pip install railtracks[sql]` or `uv add railtracks[sql]`."
            )

        self._single_column = isinstance(content_columns, str)
        self._content_columns = (
            [content_columns]
            if isinstance(content_columns, str)
            else list(content_columns)
        )
        if not self._content_columns:
            raise ValueError(
                "SQLLoader() needs at least one column in 'content_columns'."
            )
        self._content_separator = content_separator
        self._metadata_columns = metadata_columns
        self._id_column = id_column
        self._source_column = source_column
        self._table_or_query = table_or_query
        self._is_raw_query = _looks_like_query(table_or_query)
        self._ids = list(ids) if ids is not None else None

        if self._ids is not None and id_column is None:
            raise ValueError("An 'id_column' must be set when filtering by 'ids'.")

        if not self._is_raw_query:
            _validate_identifier(table_or_query, "table_or_query")
        columns: list[tuple[str | None, str]] = [
            (c, f"content_columns[{c!r}]") for c in self._content_columns
        ]
        columns += [(id_column, "id_column"), (source_column, "source_column")]
        columns += [(c, f"metadata_columns[{c!r}]") for c in metadata_columns or []]
        for column, label in columns:
            if column is not None:
                _validate_identifier(column, label)

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

    def _row_to_document(self, row: dict[str, Any], *, row_index: int) -> Document:
        missing = [col for col in self._content_columns if col not in row]
        if missing:
            available = sorted(row.keys())
            raise ValueError(
                f"content_columns {missing} were not found in the "
                f"query results. Available columns: {available}. "
                "Check that 'content_columns' matches columns returned by the query."
            )
        if self._single_column:
            content = str(row[self._content_columns[0]])
        else:
            content = labelled_join(
                ((col, str(row[col])) for col in self._content_columns),
                self._content_separator,
            )

        if self._metadata_columns is not None:
            meta = {col: row[col] for col in self._metadata_columns if col in row}
        else:
            excluded = set(self._content_columns)
            if self._id_column:
                excluded.add(self._id_column)
            meta = {k: v for k, v in row.items() if k not in excluded}

        # Namespace row keys with table_or_query so Document.id (uuid5 of
        # source) is unique across tables and across rows that share an id.
        # Try source_column, then id_column; a NULL in one does not mask the other.
        row_key = next(
            (
                str(row[col])
                for col in (self._source_column, self._id_column)
                if col and row.get(col) is not None
            ),
            # Distinct from real column values (e.g. id=1 vs NULL-at-index-1).
            f"row={row_index}",
        )
        source = f"{self._table_or_query}#{row_key}"

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

    def _fetch_by_ids(self, ids: list[str]) -> list[dict[str, Any]]:
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
            result = conn.execute(stmt, {"keys": ids})
            return [dict(row._mapping) for row in result]

    def _fetch_rows(self) -> list[dict[str, Any]]:
        if self._ids is not None:
            if not self._ids:
                return []
            return self._fetch_by_ids(self._ids)
        return self._fetch_all()

    async def astream(self) -> AsyncGenerator[Document, None]:
        """Stream documents one at a time as rows are read.

        Yields:
            Document: The next row as a document.
        """
        rows = await asyncio.to_thread(self._fetch_rows)
        if rows and self._metadata_columns is not None:
            missing = [col for col in self._metadata_columns if col not in rows[0]]
            if missing:
                warnings.warn(
                    f"metadata_columns {missing} not found in query results and will be omitted. "
                    f"Available columns: {sorted(rows[0].keys())}.",
                    stacklevel=2,
                )
        for row_index, row in enumerate(rows):
            yield self._row_to_document(row, row_index=row_index)
