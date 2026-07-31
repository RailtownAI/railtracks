"""DuckDB column-type mapping for the event registry.

The registry describes payload columns in DB-agnostic ``ColumnKind`` terms; this module
translates them into DuckDB type strings for the SQL projections in ``connect.py``.
"""

from __future__ import annotations

from railtracks.events.registry import ColumnKind, payload_columns

_KIND_TO_DUCKDB: dict[ColumnKind, str] = {
    ColumnKind.STRING: "VARCHAR",
    ColumnKind.INTEGER: "BIGINT",
    ColumnKind.FLOAT: "DOUBLE",
    ColumnKind.BOOLEAN: "BOOLEAN",
    ColumnKind.TIMESTAMP_TZ: "TIMESTAMP WITH TIME ZONE",
    ColumnKind.JSON: "JSON",
}


def duckdb_columns(namespace: str) -> dict[str, str]:
    """Return ``{payload_key: duckdb_type_string}`` for a namespace."""
    return {key: _KIND_TO_DUCKDB[kind] for key, kind in payload_columns(namespace).items()}
