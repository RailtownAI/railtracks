"""SQL query interface over the observability JSONL files.

`connect(path, namespaces)` opens a DuckDB connection with:

- An ``events`` view — the union of the path plus bundled schema samples,
  with envelope columns typed and payload kept as raw JSON. Sample rows
  are filtered out via ``scope_id != '__sample__'`` so they never leak
  into query results.
- One view per requested namespace, with the payload keys observed
  across samples + real data exploded into their own columns.

Events are assumed to carry a non-null ``scope_id`` — that's a writer-side
contract, so the sample filter's ``!=`` semantics are safe.

Namespaces are explicit. To open with everything present in a file, call
``list_namespaces(path)`` first and pass the result to ``connect``.

Lives behind the ``[visual]`` extra; DuckDB is imported lazily.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

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


_SAMPLES_DIR = Path(__file__).parent / "_samples"


def _sample_files() -> list[Path]:
    if not _SAMPLES_DIR.is_dir():
        return []
    return sorted(_SAMPLES_DIR.glob("*.jsonl"))


def _resolve_data_files(path: Path | str) -> list[Path]:
    p = Path(path)
    if p.is_file():
        return [p]
    if p.is_dir():
        return sorted(p.glob("*.jsonl"))
    return []


def _scan(files: list[Path]) -> dict[str, set[str]]:
    """One-pass discovery over the JSONL files: {namespace: {payload_keys}}."""
    result: dict[str, set[str]] = {}
    for path in files:
        with path.open(encoding="utf-8") as fh:
            for raw in fh:
                line = raw.strip()
                if not line:
                    continue
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    continue
                event_type = event.get("event_type") or ""
                if "." not in event_type:
                    continue
                namespace = event_type.split(".", 1)[0]
                bucket = result.setdefault(namespace, set())
                payload = event.get("payload")
                if isinstance(payload, dict):
                    bucket.update(payload.keys())
    return result


def list_namespaces(path: Path | str) -> list[str]:
    """Return the sorted distinct namespaces across bundled samples plus ``path``.

    Reads the files — does not open a DuckDB connection.
    """
    files = _sample_files() + _resolve_data_files(path)
    return sorted(_scan(files).keys())


def connect(path: Path | str, namespaces: list[str]) -> EventQuery:
    """Open a DuckDB connection with an ``events`` view plus one view per requested namespace.

    ``path`` is either a single ``.jsonl`` file or a directory whose
    ``*.jsonl`` children are unioned. ``namespaces`` is required — the
    subset the caller wants materialized as views. Namespaces that end up
    with real data or a bundled sample are registered; the rest land in
    ``EventQuery.namespaces_missing``.
    """
    duckdb = _require_duckdb()
    con = duckdb.connect()
    q = EventQuery(
        con=con,
        namespaces=[],
        namespaces_missing=[],
        _path=Path(path),
        _requested=list(namespaces),
    )
    q._rebuild()
    return q


@dataclass
class EventQuery:
    con: Any
    namespaces: list[str]
    namespaces_missing: list[str]
    _path: Path = field(repr=False)
    _requested: list[str] = field(repr=False)

    def refresh(self) -> None:
        """Re-scan the files and rebuild views. Mutates ``namespaces`` /
        ``namespaces_missing`` in place."""
        self._rebuild()

    def close(self) -> None:
        self.con.close()

    def __enter__(self) -> EventQuery:
        return self

    def __exit__(self, *args) -> None:
        self.close()

    def _rebuild(self) -> None:
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


__all__ = ["connect", "list_namespaces", "EventQuery"]
