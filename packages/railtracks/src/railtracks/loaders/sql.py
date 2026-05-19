from __future__ import annotations

import asyncio
import re
import warnings
from typing import TYPE_CHECKING, Any, Optional

from railtracks.vector_stores.chunking.base_chunker import Chunk

from .base import BaseStorageLoader

if TYPE_CHECKING:
    from sqlalchemy import Engine

_IDENT_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_$]*(\.[A-Za-z_][A-Za-z0-9_$]*)?$")


def _looks_like_query(s: str) -> bool:
    """Return True if *s* appears to be a raw SQL statement rather than a table name."""
    return s.strip().upper().startswith("SELECT")


def _validate_identifier(value: str, label: str) -> None:
    """Raise ValueError if *value* is not a safe SQL identifier.

    Allows simple names (``my_table``) and schema-qualified names
    (``public.documents``).  Rejects anything containing SQL metacharacters
    or whitespace that could enable injection.
    """
    if not _IDENT_RE.match(value):
        raise ValueError(
            f"Invalid SQL identifier for {label!r}: {value!r}. "
            "Identifiers must start with a letter or underscore and may only "
            "contain letters, digits, underscores, and dollar signs. "
            "Use 'schema.table' notation for schema-qualified names. "
            "Never pass user-controlled strings as identifiers."
        )


class SQLLoader(BaseStorageLoader):
    """Document loader for relational databases via SQLAlchemy.

    Reads rows from a table (or arbitrary ``SELECT`` query) and converts each
    row into a :class:`~railtracks.vector_stores.chunking.base_chunker.Chunk`.

    Works with any SQLAlchemy-compatible database including PostgreSQL,
    Supabase (PostgreSQL), MySQL, SQLite, and more.  For SQLite no extra
    driver is needed; for PostgreSQL install ``psycopg2`` or ``asyncpg``.

    Requires the ``sql`` extra: ``pip install railtracks[sql]``.

    Args:
        connection_string: SQLAlchemy database URL, e.g.
            ``"postgresql+psycopg2://user:pass@host/db"`` or
            ``"sqlite:///:memory:"``.
        table_or_query: Either a **table name** (e.g. ``"documents"``) or a
            full ``SELECT`` statement (e.g. ``"SELECT id, body FROM docs"``).
            Table names produce ``SELECT * FROM <table>``.

            .. note::
               Table names are validated against a strict allowlist
               (``[A-Za-z_][A-Za-z0-9_$]*``) at construction time.  Never
               pass user-controlled strings here.  Use raw ``SELECT`` queries
               with bound parameters for dynamic filtering.

               ``WITH`` (CTE) queries are not supported as ``table_or_query``.
               Wrap them in a subquery or use the CTE inline in a ``SELECT``:
               ``"SELECT * FROM (WITH … SELECT …) AS t"`` — or pass the CTE
               body as a regular SQL query where applicable.

        content_column: Name of the column whose value becomes
            :attr:`Chunk.content`.
        metadata_columns: Column names to include in :attr:`Chunk.metadata`.
            When ``None`` all columns except ``content_column`` and
            ``id_column`` are included.
        id_column: Column to use as :attr:`Chunk.id`.  When ``None`` a UUID
            is auto-generated for every chunk.
        document_column: Column to use as :attr:`Chunk.document`.  Falls back
            to ``id_column`` when ``None``.
        engine: An existing ``sqlalchemy.Engine`` instance. When provided,
            ``connection_string`` and ``engine_kwargs`` are ignored. Useful
            when you already have a configured engine (custom pool, SSL, etc.)
            or for testing with an in-memory database.  The caller is
            responsible for disposing this engine; :meth:`close` will not
            touch it.
        engine_kwargs: Extra keyword arguments forwarded to
            ``sqlalchemy.create_engine()``.

    Raises:
        ImportError: If ``sqlalchemy`` is not installed.
        ValueError: If an identifier argument contains unsafe characters, or
            if ``load_keys()`` is called without an ``id_column``.

    Example::

        # PostgreSQL / Supabase
        loader = SQLLoader(
            "postgresql+psycopg2://user:pass@db.supabase.co:5432/postgres",
            table_or_query="documents",
            content_column="body",
            metadata_columns=["title", "author", "created_at"],
            id_column="id",
        )
        chunks = loader.load()

        # SQLite (great for testing / local dev)
        loader = SQLLoader(
            "sqlite:///my_db.sqlite",
            table_or_query="knowledge",
            content_column="text",
        )
        chunks = loader.load()

        # Raw query
        loader = SQLLoader(
            connection_string,
            table_or_query="SELECT id, body FROM docs WHERE published = 1",
            content_column="body",
            id_column="id",
        )
        chunks = loader.load()

        # Load specific rows by id_column value
        chunks = loader.load_keys(["doc-001", "doc-002"])

        # Context-manager — engine is disposed automatically
        with SQLLoader(connection_string, "documents", "body") as loader:
            chunks = loader.load()

        # Async usage
        chunks = await loader.aload()
    """

    def __init__(
        self,
        connection_string: str,
        table_or_query: str,
        content_column: str,
        *,
        metadata_columns: Optional[list[str]] = None,
        id_column: Optional[str] = None,
        document_column: Optional[str] = None,
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
        self._document_column = document_column
        self._table_or_query = table_or_query
        self._is_raw_query = _looks_like_query(table_or_query)

        # Validate all structural identifiers at construction time.
        # Values are developer-supplied config, not end-user input — but we
        # enforce the allowlist to catch misconfiguration and make injection
        # harder if a value ever originates from an untrusted source.
        if not self._is_raw_query:
            _validate_identifier(table_or_query, "table_or_query")
        _validate_identifier(content_column, "content_column")
        if id_column is not None:
            _validate_identifier(id_column, "id_column")
        if document_column is not None:
            _validate_identifier(document_column, "document_column")
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

    # ------------------------------------------------------------------
    # Resource lifecycle
    # ------------------------------------------------------------------

    def close(self) -> None:
        """Dispose the underlying SQLAlchemy engine, releasing pooled connections.

        Only disposes engines created internally by this loader.  Engines
        supplied via the ``engine`` constructor parameter are left for the
        caller to manage.
        """
        if self._owns_engine:
            self._engine.dispose()

    def __enter__(self) -> SQLLoader:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _rows_to_chunks(self, rows: list[dict[str, Any]]) -> list[Chunk]:
        chunks: list[Chunk] = []
        for row in rows:
            if self._content_column not in row:
                available = sorted(row.keys())
                raise ValueError(
                    f"content_column {self._content_column!r} was not found in the "
                    f"query results. Available columns: {available}. "
                    "Check that 'content_column' matches a column returned by the query."
                )
            content = str(row[self._content_column])

            # Determine which columns go into metadata
            if self._metadata_columns is not None:
                meta = {col: row[col] for col in self._metadata_columns if col in row}
            else:
                excluded = {self._content_column}
                if self._id_column:
                    excluded.add(self._id_column)
                meta = {k: v for k, v in row.items() if k not in excluded}

            # Add a source hint so metadata always has a 'source' key
            meta.setdefault("source", self._table_or_query)

            chunk_id = str(row[self._id_column]) if self._id_column else None
            doc_col = self._document_column or self._id_column
            document = str(row[doc_col]) if doc_col and doc_col in row else None

            chunks.append(
                Chunk(
                    content=content,
                    id=chunk_id,
                    document=document,
                    metadata=meta,
                )
            )
        return chunks

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

    # ------------------------------------------------------------------
    # BaseStorageLoader interface
    # ------------------------------------------------------------------

    def load(self, prefix: Optional[str] = None) -> list[Chunk]:
        """Load all rows from the configured table or query.

        The ``prefix`` parameter is not meaningful for SQL sources and is
        accepted only to satisfy the :class:`BaseStorageLoader` interface.
        Passing a non-``None`` value emits a :class:`UserWarning`.

        Returns:
            list[Chunk]: All matching rows as Chunk objects.
        """
        if prefix is not None:
            warnings.warn(
                "SQLLoader does not support prefix filtering; "
                "the 'prefix' argument is ignored. "
                "Use a WHERE clause in your SQL query for row-level filtering.",
                UserWarning,
                stacklevel=2,
            )
        rows = self._fetch_all()
        return self._rows_to_chunks(rows)

    def load_keys(self, keys: list[str]) -> list[Chunk]:
        """Load specific rows by their ``id_column`` value.

        Args:
            keys: List of ``id_column`` values to fetch.

        Returns:
            list[Chunk]: Matching rows as Chunk objects.

        Raises:
            ValueError: If the loader was created without an ``id_column``.
        """
        if not self._id_column:
            raise ValueError(
                "load_keys() requires an 'id_column' to be set on the loader."
            )
        if not keys:
            return []
        rows = self._fetch_by_ids(keys)
        return self._rows_to_chunks(rows)
