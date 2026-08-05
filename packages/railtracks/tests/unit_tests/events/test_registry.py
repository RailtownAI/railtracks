"""Tests for the event registry — dataclass-driven column typing for the query layer."""

from __future__ import annotations

from dataclasses import fields

from railtracks.events.registry import (
    EVENT_CLASSES,
    ColumnKind,
    namespaces,
    payload_columns,
)


class TestNamespaces:
    def test_returns_the_known_namespaces(self):
        assert namespaces() == ["llm", "middleware", "node", "session"]


class TestPayloadColumnsLLM:
    def test_scalars_get_native_kinds(self):
        cols = payload_columns("llm")
        assert cols["llm_id"] == ColumnKind.STRING
        assert cols["model_name"] == ColumnKind.STRING
        assert cols["input_tokens"] == ColumnKind.INTEGER
        assert cols["output_tokens"] == ColumnKind.INTEGER
        assert cols["total_cost"] == ColumnKind.FLOAT
        assert cols["latency"] == ColumnKind.FLOAT
        assert cols["system_fingerprint"] == ColumnKind.STRING

    def test_timestamp_is_timestamp_tz(self):
        assert payload_columns("llm")["timestamp"] == ColumnKind.TIMESTAMP_TZ

    def test_structured_fields_become_json(self):
        cols = payload_columns("llm")
        assert cols["message_input"] == ColumnKind.JSON
        assert cols["output"] == ColumnKind.JSON
        assert cols["model_provider"] == ColumnKind.JSON  # ModelProvider enum

    def test_failure_mixin_fields_present(self):
        cols = payload_columns("llm")
        assert cols["exception_name"] == ColumnKind.STRING
        assert cols["exception_message"] == ColumnKind.STRING


class TestSpatialParentFlattening:
    def test_llm_namespace_exposes_every_spatial_parent_subfield(self):
        cols = payload_columns("llm")
        assert cols["spatial_parent_spatial_type"] == ColumnKind.STRING
        assert cols["spatial_parent_node_id"] == ColumnKind.STRING
        assert cols["spatial_parent_middleware_invoke_id"] == ColumnKind.STRING
        assert cols["spatial_parent_llm_invoke_id"] == ColumnKind.STRING

    def test_no_nested_spatial_parent_column(self):
        assert "spatial_parent" not in payload_columns("llm")
        assert "spatial_parent" not in payload_columns("node")
        assert "spatial_parent" not in payload_columns("middleware")


class TestParentFlattening:
    def test_llm_namespace_exposes_every_parent_subfield(self):
        cols = payload_columns("llm")
        assert cols["parent_parent_type"] == ColumnKind.STRING
        assert cols["parent_node_id"] == ColumnKind.STRING
        assert cols["parent_middleware_type_id"] == ColumnKind.STRING
        assert cols["parent_middleware_invoke_id"] == ColumnKind.STRING
        assert cols["parent_llm_type_id"] == ColumnKind.STRING
        assert cols["parent_llm_invoke_id"] == ColumnKind.STRING

    def test_no_nested_parent_column(self):
        assert "parent" not in payload_columns("llm")
        assert "parent" not in payload_columns("node")
        assert "parent" not in payload_columns("middleware")


class TestPayloadColumnsNode:
    def test_scalar_fields(self):
        cols = payload_columns("node")
        assert cols["node_id"] == ColumnKind.STRING
        assert cols["name"] == ColumnKind.STRING
        assert cols["node_type"] == ColumnKind.STRING

    def test_args_and_kwargs_are_json(self):
        cols = payload_columns("node")
        assert cols["args"] == ColumnKind.JSON
        assert cols["kwargs"] == ColumnKind.JSON

    def test_response_is_json(self):
        assert payload_columns("node")["response"] == ColumnKind.JSON


class TestPayloadColumnsMiddleware:
    def test_scalar_middleware_fields(self):
        cols = payload_columns("middleware")
        assert cols["middleware_type_id"] == ColumnKind.STRING
        assert cols["middleware_name"] == ColumnKind.STRING

    def test_structured_middleware_fields(self):
        cols = payload_columns("middleware")
        assert cols["message_history"] == ColumnKind.JSON
        assert cols["tools"] == ColumnKind.JSON
        assert cols["schema"] == ColumnKind.JSON
        assert cols["decision"] == ColumnKind.JSON
        assert cols["response"] == ColumnKind.JSON


class TestPayloadColumnsSession:
    def test_scalar_fields(self):
        cols = payload_columns("session")
        assert cols["session_id"] == ColumnKind.STRING
        assert cols["flow_name"] == ColumnKind.STRING
        assert cols["flow_id"] == ColumnKind.STRING
        assert cols["session_name"] == ColumnKind.STRING
        assert cols["entry_point_name"] == ColumnKind.STRING
        assert cols["status"] == ColumnKind.STRING
        assert cols["error"] == ColumnKind.STRING
        assert cols["timeout"] == ColumnKind.FLOAT
        assert cols["duration_seconds"] == ColumnKind.FLOAT
        assert cols["end_on_error"] == ColumnKind.BOOLEAN
        assert cols["save_state"] == ColumnKind.BOOLEAN


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
