"""DuckDB column-type mapping for the event registry.

The registry describes payload columns in DB-agnostic ``ColumnKind`` terms; this module
translates them into DuckDB type strings for the SQL projections in ``connect.py``.
"""

from __future__ import annotations

from railtracks.events.registry import ColumnKind, ColumnSpec, payload_columns

_KIND_TO_DUCKDB: dict[ColumnKind, str] = {
    ColumnKind.STRING: "VARCHAR",
    ColumnKind.INTEGER: "BIGINT",
    ColumnKind.FLOAT: "DOUBLE",
    ColumnKind.BOOLEAN: "BOOLEAN",
    ColumnKind.TIMESTAMP_TZ: "TIMESTAMP WITH TIME ZONE",
    ColumnKind.JSON: "JSON",
    # Keep stored discriminators as text.  The registry still records their known
    # members for validation and documentation, but a newer or older event value
    # must remain visible instead of being coerced to NULL by a physical ENUM.
    ColumnKind.ENUM: "VARCHAR",
}


def _duckdb_type(spec: ColumnSpec) -> str:
    """Render a ``ColumnSpec`` as a DuckDB type string."""
    return _KIND_TO_DUCKDB[spec.kind]


def duckdb_columns(namespace: str) -> dict[str, str]:
    """Return ``{payload_key: duckdb_type_string}`` for a namespace."""
    return {key: _duckdb_type(spec) for key, spec in payload_columns(namespace).items()}
