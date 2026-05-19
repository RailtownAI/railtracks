from __future__ import annotations

import re
import warnings
from typing import TYPE_CHECKING, Any, Literal, Optional

from railtracks.vector_stores.chunking.base_chunker import Chunk

from .base import BaseStorageWriter

if TYPE_CHECKING:
    from sqlalchemy import Engine

_IDENT_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_$]*(\.[A-Za-z_][A-Za-z0-9_$]*)?$")


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


class SQLWriter(BaseStorageWriter):
    """Document writer for relational databases via SQLAlchemy.

    Converts :class:`~railtracks.vector_stores.chunking.base_chunker.Chunk`
    objects into table rows and writes them to any SQLAlchemy-compatible
    database (PostgreSQL, Supabase, MySQL, SQLite, ...).

    In ``"upsert"`` mode (default) an existing row with the same id is replaced
    before the new row is inserted, giving safe idempotent writes.  In
    ``"insert"`` mode rows are appended without any conflict handling.

    .. note:: **All-or-nothing writes**

       All chunks in a single :meth:`write` call are persisted inside one
       database transaction.  If any individual row fails (constraint
       violation, type mismatch, etc.) the **entire batch is rolled back** and
       no rows are written.  The exception from the failing row is re-raised
       so you can inspect which chunk caused the error.  To write chunks
       individually and tolerate partial failures, call :meth:`write_key` in
       a loop with your own error handling.

    Requires the ``sql`` extra: ``pip install railtracks[sql]``.

    Args:
        connection_string: SQLAlchemy database URL, e.g.
            ``"postgresql+psycopg2://user:pass@host/db"`` or
            ``"sqlite:///my.db"``.
        table: Target table name. The table must already exist.

            .. note::
               The table name is validated against a strict allowlist at
               construction time.  Never pass user-controlled strings here.

        content_column: Column that receives :attr:`Chunk.content`.
        id_column: Column that receives :attr:`Chunk.id`. Also used as the
            conflict key for upserts. When ``None`` no id is written and
            :meth:`write_key` raises :exc:`ValueError`.
        document_column: Column that receives :attr:`Chunk.document`.
            Ignored when ``None``.
        metadata_columns: Metadata keys to persist as individual columns.
            Each key in this list is read from ``chunk.metadata`` and written
            to the column of the same name. When ``None`` no metadata columns
            are written.
        mode: ``"upsert"`` (default) deletes any existing row matching
            ``id_column`` before inserting; ``"insert"`` performs a plain
            ``INSERT``.
        engine: An existing ``sqlalchemy.Engine`` instance. When provided,
            ``connection_string`` and ``engine_kwargs`` are ignored.  The
            caller is responsible for disposing this engine; :meth:`close`
            will not touch it.
        engine_kwargs: Extra keyword arguments forwarded to
            ``sqlalchemy.create_engine()``.

    Raises:
        ImportError: If ``sqlalchemy`` is not installed.
        ValueError: If an identifier argument contains unsafe characters, or
            if :meth:`write_key` is called without ``id_column``.

    Example::

        writer = SQLWriter(
            "postgresql+psycopg2://user:pass@host/db",
            table="documents",
            content_column="body",
            id_column="id",
            metadata_columns=["title", "category"],
        )

        # Write chunks (upsert by default)
        ids = writer.write(chunks)

        # Write raw content at an explicit id
        id_ = writer.write_key("doc-42", "Revised content ...")

        # Context-manager — engine is disposed automatically
        with SQLWriter(connection_string, "documents", "body", id_column="id") as w:
            w.write(chunks)

        # Async usage
        ids = await writer.awrite(chunks)
    """

    def __init__(
        self,
        connection_string: str,
        table: str,
        content_column: str,
        *,
        id_column: Optional[str] = None,
        document_column: Optional[str] = None,
        metadata_columns: Optional[list[str]] = None,
        mode: Literal["insert", "upsert"] = "upsert",
        engine: Optional[Engine] = None,
        engine_kwargs: Optional[dict[str, Any]] = None,
    ) -> None:
        try:
            import sqlalchemy  # noqa: F401
        except ImportError:
            raise ImportError(
                "sqlalchemy is required for SQL writing. "
                "Install it via `pip install railtracks[sql]` or `uv add railtracks[sql]`."
            )

        import sqlalchemy as sa

        # Validate all structural identifiers at construction time.
        _validate_identifier(table, "table")
        _validate_identifier(content_column, "content_column")
        if id_column is not None:
            _validate_identifier(id_column, "id_column")
        if document_column is not None:
            _validate_identifier(document_column, "document_column")
        if metadata_columns is not None:
            for col in metadata_columns:
                _validate_identifier(col, f"metadata_columns[{col!r}]")

        self._table = table
        self._content_column = content_column
        self._id_column = id_column
        self._document_column = document_column
        self._metadata_columns = metadata_columns
        self._mode = mode

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
        return f"SQLWriter(url={url!r}, table={self._table!r}, mode={self._mode!r})"

    # ------------------------------------------------------------------
    # Resource lifecycle
    # ------------------------------------------------------------------

    def close(self) -> None:
        """Dispose the underlying SQLAlchemy engine, releasing pooled connections.

        Only disposes engines created internally by this writer.  Engines
        supplied via the ``engine`` constructor parameter are left for the
        caller to manage.
        """
        if self._owns_engine:
            self._engine.dispose()

    def __enter__(self) -> SQLWriter:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _chunk_to_row(self, chunk: Chunk) -> dict[str, Any]:
        row: dict[str, Any] = {self._content_column: chunk.content}
        if self._id_column and chunk.id is not None:
            row[self._id_column] = chunk.id
        if self._document_column and chunk.document is not None:
            row[self._document_column] = chunk.document
        if self._metadata_columns:
            for col in self._metadata_columns:
                if col in chunk.metadata:
                    row[col] = chunk.metadata[col]
        return row

    def _write_row(self, conn: Any, row: dict[str, Any]) -> None:
        import sqlalchemy as sa

        if self._mode == "upsert" and self._id_column and self._id_column in row:
            conn.execute(
                sa.text(
                    f"DELETE FROM {self._table} WHERE {self._id_column} = :_id"  # noqa: S608
                ),
                {"_id": row[self._id_column]},
            )

        cols = list(row.keys())
        col_str = ", ".join(cols)
        param_str = ", ".join(f":{c}" for c in cols)
        conn.execute(
            sa.text(
                f"INSERT INTO {self._table} ({col_str}) VALUES ({param_str})"  # noqa: S608
            ),
            row,
        )

    def _row_uri(self, row: dict[str, Any]) -> str:
        if self._id_column and self._id_column in row:
            return f"sql://{self._table}/{row[self._id_column]}"
        return f"sql://{self._table}"

    # ------------------------------------------------------------------
    # BaseStorageWriter interface
    # ------------------------------------------------------------------

    def write(self, chunks: list[Chunk], prefix: Optional[str] = None) -> list[str]:
        """Write chunks to the database table.

        All chunks are written inside a **single transaction**.  If any row
        fails the entire batch is rolled back and the exception is re-raised.
        See the class docstring for details on handling partial failures.

        The ``prefix`` parameter has no effect on SQL writes and is accepted
        only to satisfy the :class:`BaseStorageWriter` interface.  Passing a
        non-``None`` value emits a :class:`UserWarning`.

        Args:
            chunks: Chunk objects to persist.
            prefix: Unused for SQL; accepted for interface compatibility.

        Returns:
            list[str]: ``sql://table/id`` URIs (or ``sql://table`` when no
            ``id_column`` is configured) for every chunk written.
        """
        if prefix is not None:
            warnings.warn(
                "SQLWriter does not support prefix; "
                "the 'prefix' argument is ignored.",
                UserWarning,
                stacklevel=2,
            )
        uris: list[str] = []
        with self._engine.begin() as conn:
            for chunk in chunks:
                row = self._chunk_to_row(chunk)
                self._write_row(conn, row)
                uris.append(self._row_uri(row))
        return uris

    def write_key(self, key: str, content: str) -> str:
        """Write raw text content as a single row identified by ``key``.

        The ``key`` is stored in ``id_column``.  This method requires
        ``id_column`` to be set on the writer.

        Args:
            key: Value to store in ``id_column``.
            content: Text content stored in ``content_column``.

        Returns:
            str: ``sql://table/key`` URI of the written row.

        Raises:
            ValueError: If the writer was created without an ``id_column``.
        """
        if not self._id_column:
            raise ValueError(
                "write_key() requires an 'id_column' to be set on the writer."
            )
        row: dict[str, Any] = {
            self._id_column: key,
            self._content_column: content,
        }
        with self._engine.begin() as conn:
            self._write_row(conn, row)
        return f"sql://{self._table}/{key}"
