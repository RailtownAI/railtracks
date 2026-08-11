"""Tests for the event registry — namespace-keyed column table.

The registry is hand-maintained. The completeness test below is the safety net:
it walks every concrete event class and asserts each of its dataclass fields
is reachable through ``payload_columns`` (either directly or via
``spatial_parent_*`` / ``parent_*`` flattening).
"""

from __future__ import annotations

from dataclasses import fields

# Importing the event modules populates ``SessionEventBase.__subclasses__()``
# for the concrete-subclass walk used in ``TestRegistryCompleteness``.
from railtracks.events import llm, middleware, node, session  # noqa: F401
from railtracks.events._base import SessionEventBase
from railtracks.events.registry import (
    ColumnKind,
    ColumnSpec,
    namespaces,
    payload_columns,
)


def _kind(cols: dict[str, ColumnSpec], key: str) -> ColumnKind:
    return cols[key].kind


def _concrete_event_classes() -> list[type[SessionEventBase]]:
    """Every leaf subclass of ``SessionEventBase`` (skips abstract intermediaries)."""
    seen: set[type[SessionEventBase]] = set()

    def walk(cls: type) -> None:
        for sub in cls.__subclasses__():
            if not getattr(sub, "__abstractmethods__", None):
                seen.add(sub)
            walk(sub)

    walk(SessionEventBase)
    return sorted(seen, key=lambda c: c.__name__)


class TestNamespaces:
    def test_returns_the_known_namespaces(self):
        assert namespaces() == ["llm", "middleware", "node", "session"]


class TestPayloadColumnsLLM:
    def test_scalars_get_native_kinds(self):
        cols = payload_columns("llm")
        assert _kind(cols, "llm_id") == ColumnKind.STRING
        assert _kind(cols, "model_name") == ColumnKind.STRING
        assert _kind(cols, "input_tokens") == ColumnKind.INTEGER
        assert _kind(cols, "output_tokens") == ColumnKind.INTEGER
        assert _kind(cols, "total_cost") == ColumnKind.FLOAT
        assert _kind(cols, "latency") == ColumnKind.FLOAT
        assert _kind(cols, "system_fingerprint") == ColumnKind.STRING

    def test_timestamp_is_timestamp_tz(self):
        assert _kind(payload_columns("llm"), "timestamp") == ColumnKind.TIMESTAMP_TZ

    def test_structured_fields_become_json(self):
        cols = payload_columns("llm")
        assert _kind(cols, "message_input") == ColumnKind.JSON
        assert _kind(cols, "output") == ColumnKind.JSON

    def test_model_provider_enum_covers_every_value(self):
        from railtracks.llm.providers import ModelProvider

        spec = payload_columns("llm")["model_provider"]
        assert spec.kind == ColumnKind.ENUM
        assert set(spec.enum_members or ()) == {m.value for m in ModelProvider}

    def test_failure_mixin_fields_present(self):
        cols = payload_columns("llm")
        assert _kind(cols, "exception_name") == ColumnKind.STRING
        assert _kind(cols, "exception_message") == ColumnKind.STRING


class TestSpatialParentFlattening:
    def test_llm_namespace_exposes_every_spatial_parent_subfield(self):
        cols = payload_columns("llm")
        assert _kind(cols, "spatial_parent_spatial_type") == ColumnKind.ENUM
        assert _kind(cols, "spatial_parent_node_id") == ColumnKind.STRING
        assert _kind(cols, "spatial_parent_middleware_invoke_id") == ColumnKind.STRING
        assert _kind(cols, "spatial_parent_llm_invoke_id") == ColumnKind.STRING

    def test_spatial_type_enum_covers_every_subclass_value(self):
        spec = payload_columns("llm")["spatial_parent_spatial_type"]
        assert spec.kind == ColumnKind.ENUM
        assert set(spec.enum_members or ()) == {
            "none",
            "node",
            "middleware",
            "node_and_middleware",
            "llm_and_middleware",
        }

    def test_no_nested_spatial_parent_column(self):
        assert "spatial_parent" not in payload_columns("llm")
        assert "spatial_parent" not in payload_columns("node")
        assert "spatial_parent" not in payload_columns("middleware")


class TestParentFlattening:
    def test_llm_namespace_exposes_every_parent_subfield(self):
        cols = payload_columns("llm")
        assert _kind(cols, "parent_parent_type") == ColumnKind.ENUM
        assert _kind(cols, "parent_node_id") == ColumnKind.STRING
        assert _kind(cols, "parent_middleware_type_id") == ColumnKind.STRING
        assert _kind(cols, "parent_middleware_invoke_id") == ColumnKind.STRING
        assert _kind(cols, "parent_llm_type_id") == ColumnKind.STRING
        assert _kind(cols, "parent_llm_invoke_id") == ColumnKind.STRING

    def test_parent_type_enum_covers_every_subclass_value(self):
        spec = payload_columns("llm")["parent_parent_type"]
        assert spec.kind == ColumnKind.ENUM
        assert set(spec.enum_members or ()) == {"node", "middleware", "llm"}

    def test_no_nested_parent_column(self):
        assert "parent" not in payload_columns("llm")
        assert "parent" not in payload_columns("node")
        assert "parent" not in payload_columns("middleware")


class TestPayloadColumnsNode:
    def test_scalar_fields(self):
        cols = payload_columns("node")
        assert _kind(cols, "node_id") == ColumnKind.STRING
        assert _kind(cols, "name") == ColumnKind.STRING
        assert _kind(cols, "node_type") == ColumnKind.STRING

    def test_args_and_kwargs_are_json(self):
        cols = payload_columns("node")
        assert _kind(cols, "args") == ColumnKind.JSON
        assert _kind(cols, "kwargs") == ColumnKind.JSON

    def test_response_is_json(self):
        assert _kind(payload_columns("node"), "response") == ColumnKind.JSON


class TestPayloadColumnsMiddleware:
    def test_scalar_middleware_fields(self):
        cols = payload_columns("middleware")
        assert _kind(cols, "middleware_type_id") == ColumnKind.STRING
        assert _kind(cols, "middleware_name") == ColumnKind.STRING

    def test_structured_middleware_fields(self):
        cols = payload_columns("middleware")
        assert _kind(cols, "message_history") == ColumnKind.JSON
        assert _kind(cols, "tools") == ColumnKind.JSON
        assert _kind(cols, "schema") == ColumnKind.JSON
        assert _kind(cols, "decision") == ColumnKind.JSON
        assert _kind(cols, "response") == ColumnKind.JSON


class TestPayloadColumnsSession:
    def test_scalar_fields(self):
        cols = payload_columns("session")
        assert _kind(cols, "session_id") == ColumnKind.STRING
        assert _kind(cols, "flow_name") == ColumnKind.STRING
        assert _kind(cols, "flow_id") == ColumnKind.STRING
        assert _kind(cols, "session_name") == ColumnKind.STRING
        assert _kind(cols, "entry_point_name") == ColumnKind.STRING
        assert _kind(cols, "error") == ColumnKind.STRING
        assert _kind(cols, "timeout") == ColumnKind.FLOAT
        assert _kind(cols, "duration_seconds") == ColumnKind.FLOAT
        assert _kind(cols, "end_on_error") == ColumnKind.BOOLEAN
        assert _kind(cols, "save_state") == ColumnKind.BOOLEAN

    def test_status_is_enum_of_success_and_failure(self):
        spec = payload_columns("session")["status"]
        assert spec.kind == ColumnKind.ENUM
        assert set(spec.enum_members or ()) == {"success", "failure"}


class TestUnknownNamespace:
    def test_returns_empty_dict(self):
        assert payload_columns("nope") == {}
        assert payload_columns("") == {}


class TestRegistryCompleteness:
    """Drift check — the hand-maintained table has to keep pace with the event dataclasses.

    Fires if you added a field or a new event class and forgot to update
    ``NAMESPACE_COLUMNS`` in ``registry.py``.
    """

    def test_taxonomy_has_expected_size(self):
        classes = _concrete_event_classes()
        assert len(classes) >= 32

    def test_every_dataclass_field_appears_as_a_column(self):
        for cls in _concrete_event_classes():
            # Concrete events implement ``event_type()`` as a literal, so an
            # uninitialized instance is enough to read the namespace off it.
            namespace = cls.__new__(cls).event_type().split(".", 1)[0]
            cols = payload_columns(namespace)
            for f in fields(cls):
                if f.name == "spatial_parent":
                    assert "spatial_parent_spatial_type" in cols, cls
                elif f.name == "parent":
                    assert "parent_parent_type" in cols, cls
                else:
                    assert f.name in cols, f"{cls.__name__}.{f.name} missing"
