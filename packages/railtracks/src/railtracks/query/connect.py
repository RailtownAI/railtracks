from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from railtracks.cli.io import print_error, print_status
from railtracks.events.registry import NAMESPACE_COLUMNS
from railtracks.events.registry import namespaces as _registry_namespaces

from .read import resolve_data_files
from .schema import duckdb_columns

if TYPE_CHECKING:
    from duckdb import DuckDBPyConnection


_INSTALL_HINT = "pip install 'railtracks[visual]'"

_ENVELOPE_COLUMNS: dict[str, str] = {
    "event_id": "VARCHAR",
    "event_type": "VARCHAR",
    "scope_type": "VARCHAR",
    "scope_id": "VARCHAR",
    "parent_scope_id": "VARCHAR",
    "stamp": "TIMESTAMP WITH TIME ZONE",
    "payload": "JSON",
}


def _assert_no_envelope_collisions() -> None:
    """The registry must not declare payload columns that share a name with an
    envelope column, or ``CREATE VIEW`` would emit duplicate columns. Runs at
    import time so a bad registry fails fast."""
    reserved = frozenset(_ENVELOPE_COLUMNS)
    for ns, cols in NAMESPACE_COLUMNS.items():
        clash = set(cols) & reserved
        if clash:
            raise RuntimeError(
                f"registry namespace {ns!r} declares payload keys that collide "
                f"with envelope columns: {sorted(clash)}"
            )


_assert_no_envelope_collisions()


def _require_duckdb():
    try:
        import duckdb
    except ImportError as e:
        raise ImportError(
            f"railtracks.query requires the 'duckdb' package. Install with: {_INSTALL_HINT}"
        ) from e
    return duckdb


def connect(path: Path | str, namespaces: list[str]) -> EventQuery:
    """Requested namespaces backed by an event dataclass are registered as views;
    the rest land in ``EventQuery.namespaces_missing``."""
    duckdb = _require_duckdb()
    return EventQuery(duckdb.connect(), path, namespaces)


class EventQuery:
    def __init__(
        self,
        con: DuckDBPyConnection,
        path: Path | str,
        namespaces: list[str],
    ) -> None:
        self.con = con
        self.namespaces: list[str] = []
        self.namespaces_missing: list[str] = []
        self._path = Path(path)
        self._requested = list(namespaces)
        self.refresh()

    def close(self) -> None:
        self.con.close()

    def __enter__(self) -> EventQuery:
        return self

    def __exit__(self, *_exc_info) -> None:
        self.close()

    def refresh(self) -> None:
        """Re-read the data files and rebuild the views. Mutates ``namespaces`` /
        ``namespaces_missing`` in place."""
        data_files = resolve_data_files(self._path)

        self._teardown_views()
        if not data_files:
            self.namespaces, self.namespaces_missing = [], list(self._requested)
            return

        self._build_events_view(data_files)
        self._build_namespace_views()

    def _teardown_views(self) -> None:
        """Drop any views that were created for the requested namespaces, and the events view."""
        for ns in self._requested:
            self.con.execute(f"DROP VIEW IF EXISTS {_sql_identifier(ns)}")
        self.con.execute("DROP VIEW IF EXISTS events")

    def _build_events_view(self, files: list[Path]) -> None:
        """Create a view named ``events`` that unions all the JSONL files together."""
        self.con.read_json(
            [str(p) for p in files],  # type: ignore[arg-type] typing issue in duckdb
            format="newline_delimited",
            columns=_ENVELOPE_COLUMNS,
        ).create_view("events", replace=True)

    def _build_namespace_views(self) -> None:
        """Create views for each requested namespace that has a dataclass backing it."""
        registry_ns = set(_registry_namespaces())
        registered, missing = [], []
        for ns in self._requested:
            if ns in registry_ns:
                _register_namespace_view(self.con, ns)
                registered.append(ns)
            else:
                missing.append(ns)
        self.namespaces = registered
        self.namespaces_missing = missing
        print_status(
            f"Registered {len(registered)} namespaces: {registered}; "
            f"missing {len(missing)} namespaces: {missing}"
        )


def _register_namespace_view(con, namespace: str) -> None:
    """Create a view for a namespace, exposing envelope columns and typed payload columns."""
    envelope_cols = [c for c in _ENVELOPE_COLUMNS if c != "payload"]
    projections = list(envelope_cols)
    for key, duckdb_type in duckdb_columns(namespace).items():
        projections.append(_project_payload_key(key, duckdb_type))

    try:
        con.execute(
            f"CREATE VIEW {_sql_identifier(namespace)} AS "
            f"SELECT {', '.join(projections)} "
            "FROM events "
            f"WHERE event_type LIKE {_sql_string(namespace + '.%')}"
        )
    except Exception as e:
        print_error(
            f"Failed to create view for namespace {namespace!r}: {e}"
        )
        raise


def _project_payload_key(key: str, duckdb_type: str) -> str:
    """Return a SQL projection clause for ``payload['<key>']`` with the right operator.

    - ``VARCHAR`` uses ``payload->>'key'`` so the raw text comes back without JSON quotes.
    - ``JSON`` uses ``payload->'key'`` — keeps the native JSON so nested access works.
    - ``ENUM(...)`` casts ``payload->>'key'`` (unquoted text) into the enum; casting
      from JSON keeps the surrounding quotes and would break the enum lookup.
    - Everything else casts ``payload->'key'`` (native JSON) to the target duckdb type.
    """
    if duckdb_type == "VARCHAR":
        return f"payload->>{_sql_string(key)} AS {_sql_identifier(key)}"
    if duckdb_type == "JSON":
        return f"payload->{_sql_string(key)} AS {_sql_identifier(key)}"
    if duckdb_type.startswith("ENUM("):
        return f"CAST(payload->>{_sql_string(key)} AS {duckdb_type}) AS {_sql_identifier(key)}"
    return f"CAST(payload->{_sql_string(key)} AS {duckdb_type}) AS {_sql_identifier(key)}"


def _sql_string(value: str) -> str:
    """Return a SQL string literal for the given value, escaping single quotes."""
    return "'" + value.replace("'", "''") + "'"


def _sql_identifier(value: str) -> str:
    """Return a SQL identifier for the given value, escaping double quotes."""
    return '"' + value.replace('"', '""') + '"'
