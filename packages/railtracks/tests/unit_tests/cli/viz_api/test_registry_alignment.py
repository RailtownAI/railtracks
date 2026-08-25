"""Registry ↔ SQL alignment for the visualizer query layer.

The completeness test in ``tests/unit_tests/events/test_registry.py`` covers the
*dataclass → registry* boundary: every field on every concrete event class must
be reachable through ``payload_columns``. This module covers the two boundaries
the pipeline crosses on the way to the visualizer, which the dataclass check
cannot see:

1. **Query → registry.** Every ``payload->>'X'`` / ``payload->'X'`` extraction
   in a ``queries/*.py`` module must name a key the registry (or the envelope)
   declares. Rename ``spatial_parent_node_id`` in the registry without touching
   ``queries/events.py`` and the extraction silently yields NULL: no error at
   query time, and the endpoint returns rows with a null column that used to
   carry a value.

2. **Registry → DuckDB view.** The DuckDB namespace views must expose exactly
   the envelope columns (minus ``payload``) and every registry-declared payload
   column for that namespace. A projection that dropped or renamed a column
   would leave any SQL fragment referencing it to raise a binder error only at
   the moment the query fires — the test moves that discovery to import time,
   over an in-memory fixture.
"""

from __future__ import annotations

import json
import re
from contextlib import closing
from pathlib import Path

import duckdb  # noqa: F401 - imported so pytest surfaces "install duckdb" clearly
import pytest

from railtracks.cli.viz_api import queries as _queries_pkg
from railtracks.events.registry import NAMESPACE_COLUMNS
from railtracks.query import connect

# Matches ``payload->>'name'`` and ``payload->'name'``. The regex covers the
# whitespace variants DuckDB accepts because SQL fragments in this repo split
# COALESCEs across lines.
_PAYLOAD_ACCESS = re.compile(
    r"""payload\s*->>?\s*'([a-zA-Z_][a-zA-Z0-9_]*)'"""
)

# Envelope columns are hardcoded in ``railtracks.query.connect._ENVELOPE_COLUMNS``.
# Duplicated here rather than imported so a rename on either side surfaces here.
_ENVELOPE_KEYS = frozenset(
    {
        "event_id",
        "event_type",
        "scope_type",
        "scope_id",
        "parent_scope_id",
        "stamp",
        "payload",
    }
)

_QUERIES_DIR = Path(_queries_pkg.__file__).parent


def _registered_payload_keys() -> set[str]:
    """Every payload key any namespace declares, plus the envelope keys."""
    keys = set(_ENVELOPE_KEYS)
    for cols in NAMESPACE_COLUMNS.values():
        keys.update(cols)
    return keys


def _payload_accesses_in(path: Path) -> set[str]:
    return set(_PAYLOAD_ACCESS.findall(path.read_text(encoding="utf-8")))


class TestQueryPayloadKeysAreRegistered:
    """Every ``payload->>'X'`` / ``payload->'X'`` in a queries module must name a
    registered key. A miss here reads as NULL at query time with no error."""

    def test_every_payload_access_is_registered(self):
        registered = _registered_payload_keys()
        offenders: list[tuple[str, str]] = []
        for path in sorted(_QUERIES_DIR.glob("*.py")):
            for key in sorted(_payload_accesses_in(path)):
                if key not in registered:
                    offenders.append((path.name, key))
        assert not offenders, (
            "queries/*.py references payload key(s) not in NAMESPACE_COLUMNS "
            "or the envelope — a rename in the registry has drifted from the "
            "SQL: " + ", ".join(f"{name}:'{key}'" for name, key in offenders)
        )


class TestNamespaceViewMatchesRegistry:
    """The DuckDB namespace view exposes exactly the envelope columns (minus
    ``payload``) and every registry-declared payload column. Any drop or
    rename would leave a query referencing the column to error at execution
    time; this catches it at import time."""

    @pytest.fixture(scope="class")
    def events_dir(self, tmp_path_factory: pytest.TempPathFactory) -> Path:
        """A minimal JSONL stream carrying one well-formed event per namespace,
        so every namespace view is built and can be described."""
        events_dir = tmp_path_factory.mktemp("registry-alignment")
        seed = [
            {
                "event_id": "sess-0",
                "event_type": "session.started",
                "scope_type": "session",
                "scope_id": "sess-0",
                "parent_scope_id": None,
                "stamp": "2026-01-01T00:00:00+00:00",
                "payload": {
                    "timestamp": "2026-01-01T00:00:00+00:00",
                    "session_id": "sess-0",
                    "entry_point_name": "entry",
                    "end_on_error": False,
                    "save_state": False,
                },
            },
            {
                "event_id": "node-0",
                "event_type": "node.creation",
                "scope_type": "session",
                "scope_id": "sess-0",
                "parent_scope_id": None,
                "stamp": "2026-01-01T00:00:00+00:00",
                "payload": {
                    "timestamp": "2026-01-01T00:00:00+00:00",
                    "node_id": "node-0",
                    "name": "root",
                    "node_type": "Agent",
                },
            },
            {
                "event_id": "llm-0",
                "event_type": "llm.creation",
                "scope_type": "session",
                "scope_id": "sess-0",
                "parent_scope_id": None,
                "stamp": "2026-01-01T00:00:00+00:00",
                "payload": {
                    "timestamp": "2026-01-01T00:00:00+00:00",
                    "llm_id": "llm-0",
                    "model_provider": "openai",
                    "model_name": "gpt-4o",
                },
            },
            {
                "event_id": "mw-0",
                "event_type": "middleware.creation",
                "scope_type": "session",
                "scope_id": "sess-0",
                "parent_scope_id": None,
                "stamp": "2026-01-01T00:00:00+00:00",
                "payload": {
                    "timestamp": "2026-01-01T00:00:00+00:00",
                    "middleware_type_id": "mw-0",
                    "middleware_name": "guard",
                },
            },
        ]
        (events_dir / "sess-0.jsonl").write_text(
            "".join(json.dumps(event) + "\n" for event in seed),
            encoding="utf-8",
        )
        return events_dir

    @pytest.mark.parametrize("namespace", sorted(NAMESPACE_COLUMNS))
    def test_view_exposes_envelope_plus_registered_payload_columns(
        self, namespace: str, events_dir: Path
    ):
        with closing(connect(events_dir, [namespace])) as query:
            view_columns = {
                row[0]
                for row in query.con.execute(f"DESCRIBE {namespace}").fetchall()
            }
        envelope = _ENVELOPE_KEYS - {"payload"}
        expected = envelope | set(NAMESPACE_COLUMNS[namespace])
        assert view_columns == expected, (
            f"namespace view {namespace!r} exposes {view_columns - expected} "
            f"extra and is missing {expected - view_columns} — the registry "
            "has drifted from the projection in query/connect.py."
        )
