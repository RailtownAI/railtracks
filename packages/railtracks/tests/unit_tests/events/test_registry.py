"""Tests for the event registry — dataclass-driven column typing for the query layer."""

from __future__ import annotations

from dataclasses import fields

from railtracks.events.registry import (
    EVENT_CLASSES,
    ColumnKind,
    ColumnSpec,
    namespaces,
    payload_columns,
)


def _kind(cols: dict[str, ColumnSpec], key: str) -> ColumnKind:
    return cols[key].kind


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
        assert _kind(cols, "model_provider") == ColumnKind.JSON  # ModelProvider enum

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
        # The union of Literal[SpatialType.X] across every SpatialParent subclass.
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
        # SessionCompleted.status: Literal["success", "failure"] — a plain-string
        # Literal picks up ENUM detection too, not just str-Enum-based ones.
        spec = payload_columns("session")["status"]
        assert spec.kind == ColumnKind.ENUM
        assert set(spec.enum_members or ()) == {"success", "failure"}


class TestUnknownNamespace:
    def test_returns_empty_dict(self):
        assert payload_columns("nope") == {}
        assert payload_columns("") == {}


class TestRegistryCompleteness:
    def test_every_event_class_contributes_at_least_one_column(self):
        seen_namespaces = {n for n in namespaces() if payload_columns(n)}
        assert seen_namespaces == {"llm", "middleware", "node", "session"}
        assert len(EVENT_CLASSES) >= 32  # sanity — matches the current taxonomy

    def test_every_dataclass_field_appears_as_a_column(self):
        """Every field on every event class must be reachable via ``payload_columns``,
        either as a top-level column or via ``spatial_parent_*`` / ``parent_*``."""
        from railtracks.events.registry import _namespace_of

        for cls in EVENT_CLASSES:
            cols = payload_columns(_namespace_of(cls))
            for f in fields(cls):
                if f.name == "spatial_parent":
                    assert "spatial_parent_spatial_type" in cols, cls
                elif f.name == "parent":
                    assert "parent_parent_type" in cols, cls
                else:
                    assert f.name in cols, f"{cls.__name__}.{f.name} missing"
