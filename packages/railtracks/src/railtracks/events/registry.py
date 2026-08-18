"""Event registry: the source of truth for what payload columns each namespace exposes.

``payload_columns(namespace)`` returns ``{column_name: ColumnSpec}`` for the given
namespace. ``ColumnSpec`` stays storage-agnostic; ``query/schema.py`` translates
it to a DuckDB type string.

MAINTENANCE NOTE
---------------------
This file is a hand-maintained table, not derived from the event dataclasses.
If you rename or remove a field on any event class, add a new field, add a new
event class, or add a new discriminator value on ``SpatialType`` / ``ParentType``,
update ``NAMESPACE_COLUMNS`` below. The completeness test in
``tests/unit_tests/events/test_registry.py`` walks every event class and asserts
each of its dataclass fields is reachable here to verify
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from railtracks.llm.providers import ModelProvider

from ._base import ParentType, SpatialType


class ColumnKind(str, Enum):
    STRING = "string"
    INTEGER = "integer"
    FLOAT = "float"
    BOOLEAN = "boolean"
    TIMESTAMP_TZ = "timestamp_tz"
    JSON = "json"
    ENUM = "enum"


@dataclass(frozen=True)
class ColumnSpec:
    kind: ColumnKind
    enum_members: tuple[str, ...] | None = None


STRING = ColumnSpec(ColumnKind.STRING)
INTEGER = ColumnSpec(ColumnKind.INTEGER)
FLOAT = ColumnSpec(ColumnKind.FLOAT)
BOOLEAN = ColumnSpec(ColumnKind.BOOLEAN)
TIMESTAMP = ColumnSpec(ColumnKind.TIMESTAMP_TZ)
JSON = ColumnSpec(ColumnKind.JSON)


def _enum(*members: str) -> ColumnSpec:
    return ColumnSpec(ColumnKind.ENUM, enum_members=tuple(sorted(set(members))))


# ---- reusable blocks -------------------------------------------------------
_SPATIAL_PARENT: dict[str, ColumnSpec] = {
    "spatial_parent_type": _enum(*(m.value for m in SpatialType)),
    "spatial_parent_node_id": STRING,
    "spatial_parent_middleware_invoke_id": STRING,
    "spatial_parent_llm_invoke_id": STRING,
}

_PARENT: dict[str, ColumnSpec] = {
    "parent_type": _enum(*(m.value for m in ParentType)),
    "parent_node_id": STRING,
    "parent_middleware_type_id": STRING,
    "parent_middleware_invoke_id": STRING,
    "parent_llm_type_id": STRING,
    "parent_llm_invoke_id": STRING,
}

# Every event carries ``timestamp`` from SessionEventBase.
_BASE: dict[str, ColumnSpec] = {"timestamp": TIMESTAMP}

# Creation events carry spatial_parent (always NoSpatialParent at runtime, but
# the flat column shape stays uniform) and no ``parent``. Parent events layer
# the ``parent`` flattening on top.
_CREATION = {**_BASE, **_SPATIAL_PARENT}
_PARENT_EVENT = {**_CREATION, **_PARENT}
_FAILURE = {"exception_name": STRING, "exception_message": STRING}


# ---- the table -------------------------------------------------------------

NAMESPACE_COLUMNS: dict[str, dict[str, ColumnSpec]] = {
    "llm": {
        **_PARENT_EVENT,
        "llm_id": STRING,
        "model_provider": _enum(*(m.value for m in ModelProvider)),
        "model_name": STRING,
        "reported_model_name": STRING,
        "message_input": JSON,
        "output": JSON,
        "input_tokens": INTEGER,
        "output_tokens": INTEGER,
        "total_cost": FLOAT,
        "system_fingerprint": STRING,
        "latency": FLOAT,
        **_FAILURE,
    },
    "node": {
        **_PARENT_EVENT,
        "node_id": STRING,
        "name": STRING,
        "node_type": STRING,
        "args": JSON,
        "kwargs": JSON,
        "response": JSON,
        "duration_seconds": FLOAT,
        **_FAILURE,
    },
    "middleware": {
        **_PARENT_EVENT,
        "middleware_type_id": STRING,
        "middleware_name": STRING,
        "args": JSON,
        "kwargs": JSON,
        "response": JSON,
        "message_history": JSON,
        "tools": JSON,
        "schema": JSON,
        "decision": JSON,
        **_FAILURE,
    },
    "session": {
        **_CREATION,
        "session_id": STRING,
        "flow_name": STRING,
        "flow_id": STRING,
        "session_name": STRING,
        "entry_point_name": STRING,
        "timeout": FLOAT,
        "end_on_error": BOOLEAN,
        "save_state": BOOLEAN,
        "status": _enum("success", "failure"),
        "error": STRING,
        "duration_seconds": FLOAT,
    },
}


def payload_columns(namespace: str) -> dict[str, ColumnSpec]:
    """Columns exposed by ``namespace``. Unknown namespaces return ``{}``."""
    return dict(NAMESPACE_COLUMNS.get(namespace, {}))


def namespaces() -> list[str]:
    return sorted(NAMESPACE_COLUMNS)
