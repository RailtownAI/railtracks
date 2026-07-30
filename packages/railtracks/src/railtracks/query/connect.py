from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from .read import _resolve_data_files, _sample_files, _scan


_INSTALL_HINT = "pip install 'railtracks[visual]'"
_SAMPLE_SCOPE_ID = "__sample__"

_ENVELOPE_COLUMNS: dict[str, str] = {
    "event_id": "VARCHAR",
    "event_type": "VARCHAR",
    "scope_type": "VARCHAR",
    "scope_id": "VARCHAR",
    "parent_scope_id": "VARCHAR",
    "parent_event_id": "VARCHAR",
    "stamp": "JSON",
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

if TYPE_CHECKING:
    from duckdb import DuckDBPyConnection

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
        found = _scan(all_files)

        # Drop namespace views first (they depend on events), then events.
        for ns in self._requested:
            self.con.execute(f"DROP VIEW IF EXISTS {_sql_identifier(ns)}")
        self.con.execute("DROP VIEW IF EXISTS events")

        if all_files:
            self.con.execute(
                "CREATE VIEW events AS "
                f"SELECT * FROM {_read_json_expr(all_files)} "
                f"WHERE scope_id != {_sql_string(_SAMPLE_SCOPE_ID)}"
            )

        registered: list[str] = []
        missing: list[str] = []
        for ns in self._requested:
            if all_files and ns in found:
                _register_namespace_view(self.con, ns, sorted(found[ns]))
                registered.append(ns)
            else:
                missing.append(ns)

        self.namespaces = registered
        self.namespaces_missing = missing


def _register_namespace_view(con, namespace: str, payload_keys: list[str]) -> None:
    envelope_cols = [c for c in _ENVELOPE_COLUMNS if c != "payload"]
    # Payload keys that collide with envelope columns are dropped — envelope wins.
    exposed = [k for k in payload_keys if k not in _ENVELOPE_COLUMNS]
    projections = list(envelope_cols)
    for key in exposed:
        projections.append(f"payload->>{_sql_string(key)} AS {_sql_identifier(key)}")
    con.execute(
        f"CREATE VIEW {_sql_identifier(namespace)} AS "
        f"SELECT {', '.join(projections)} "
        "FROM events "
        f"WHERE event_type LIKE {_sql_string(namespace + '.%')}"
    )


def _read_json_expr(files: list[Path]) -> str:
    file_list = "[" + ", ".join(_sql_string(str(p)) for p in files) + "]"
    columns = "{" + ", ".join(
        f"{_sql_string(k)}: {_sql_string(v)}" for k, v in _ENVELOPE_COLUMNS.items()
    ) + "}"
    return f"read_json({file_list}, format='newline_delimited', columns={columns})"


def _sql_string(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def _sql_identifier(value: str) -> str:
    return '"' + value.replace('"', '""') + '"'
