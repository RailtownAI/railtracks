from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from railtracks.cli.io import print_error, print_status, print_warning

from .read import _resolve_data_files, _sample_files, _scan

if TYPE_CHECKING:
    from duckdb import DuckDBPyConnection


_INSTALL_HINT = "pip install 'railtracks[visual]'"
_SAMPLE_SCOPE_ID = "__sample__"

_ENVELOPE_COLUMNS: dict[str, str] = {
    "event_id": "VARCHAR",
    "event_type": "VARCHAR",
    "scope_type": "VARCHAR",
    "scope_id": "VARCHAR",
    "parent_scope_id": "VARCHAR",
    "stamp": "TIMESTAMP WITH TIME ZONE",
    "payload": "JSON",
}


def _require_duckdb():
    try:
        import duckdb
    except ImportError as e:
        raise ImportError(
            f"railtracks.query requires the 'duckdb' package. Install with: {_INSTALL_HINT}"
        ) from e
    return duckdb


def connect(path: Path | str, namespaces: list[str]) -> EventQuery:
    """Requested namespaces present in samples or in ``path`` are registered as views;
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
        """Re-scan the files and rebuild the views. Mutates ``namespaces`` /
        ``namespaces_missing`` in place."""
        sample_files = _sample_files()
        data_files = _resolve_data_files(self._path)
        all_files = sample_files + data_files

        self._teardown_views()
        if not all_files:
            self.namespaces, self.namespaces_missing = [], list(self._requested)
            return

        self._build_events_view(all_files)
        self._build_namespace_views(_scan(all_files))

    def _teardown_views(self) -> None:
        """Drop any views that were created for the requested namespaces, and the events view."""
        for ns in self._requested:
            self.con.execute(f"DROP VIEW IF EXISTS {_sql_identifier(ns)}")
        self.con.execute("DROP VIEW IF EXISTS events")

    def _build_events_view(self, files: list[Path]) -> None:
        """Create a view named ``events`` that unions all the JSONL files together."""
        raw = self.con.read_json(
            [str(p) for p in files],  # type: ignore[arg-type] typing issue in duckdb
            format="newline_delimited",
            columns=_ENVELOPE_COLUMNS,
        )
        raw.filter(f"scope_id != '{_SAMPLE_SCOPE_ID}'").create_view(
            "events", replace=True
        )

    def _build_namespace_views(self, found: dict[str, set[str]]) -> None:
        """Create views for each requested namespace."""
        registered, missing = [], []
        for ns in self._requested:
            if ns in found:
                _register_namespace_view(self.con, ns, sorted(found[ns]))
                registered.append(ns)
            else:
                missing.append(ns)
        self.namespaces = registered
        self.namespaces_missing = missing
        print_status(
            f"Registered {len(registered)} namespaces: {registered}; "
            f"missing {len(missing)} namespaces: {missing}"
        )


def _register_namespace_view(con, namespace: str, payload_keys: list[str]) -> None:
    """Create a view for a namespace, exposing envelope columns and payload keys."""
    envelope_cols = [c for c in _ENVELOPE_COLUMNS if c != "payload"]
    collided = [k for k in payload_keys if k in _ENVELOPE_COLUMNS]
    if collided:
        print_warning(
            f"namespace {namespace!r}: payload keys {collided} collide with envelope columns and were dropped"
        )
    exposed = [k for k in payload_keys if k not in _ENVELOPE_COLUMNS]
    projections = list(envelope_cols)
    for key in exposed:
        projections.append(f"payload->>{_sql_string(key)} AS {_sql_identifier(key)}")

    try:
        con.execute(
            f"CREATE VIEW {_sql_identifier(namespace)} AS "
            f"SELECT {', '.join(projections)} "
            "FROM events "
            f"WHERE event_type LIKE {_sql_string(namespace + '.%')}"
        )
    except Exception as e:
        print_error(
            f"Failed to create view for namespace {namespace!r} with payload keys {exposed}: {e}"
        )
        raise


def _sql_string(value: str) -> str:
    """Return a SQL string literal for the given value, escaping single quotes."""
    return "'" + value.replace("'", "''") + "'"


def _sql_identifier(value: str) -> str:
    """Return a SQL identifier for the given value, escaping double quotes."""
    return '"' + value.replace('"', '""') + '"'
