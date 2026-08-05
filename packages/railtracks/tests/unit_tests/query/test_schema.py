"""Tests for railtracks.query.schema — ColumnKind → DuckDB type mapping."""

from __future__ import annotations

from railtracks.query.schema import duckdb_columns


class TestDuckdbColumnsLLM:
    def test_scalars_map_to_native_duckdb_types(self):
        cols = duckdb_columns("llm")
        assert cols["llm_id"] == "VARCHAR"
        assert cols["input_tokens"] == "BIGINT"
        assert cols["output_tokens"] == "BIGINT"
        assert cols["total_cost"] == "DOUBLE"
        assert cols["latency"] == "DOUBLE"

    def test_timestamp_is_timestamptz(self):
        assert duckdb_columns("llm")["timestamp"] == "TIMESTAMP WITH TIME ZONE"

    def test_structured_fields_are_json(self):
        cols = duckdb_columns("llm")
        assert cols["message_input"] == "JSON"
        assert cols["output"] == "JSON"


class TestDuckdbColumnsFlattening:
    def test_spatial_parent_subfields_are_flat_varchar_columns(self):
        cols = duckdb_columns("llm")
        assert cols["spatial_parent_spatial_type"] == "VARCHAR"
        assert cols["spatial_parent_node_id"] == "VARCHAR"

    def test_parent_subfields_are_flat_varchar_columns(self):
        cols = duckdb_columns("llm")
        assert cols["parent_parent_type"] == "VARCHAR"
        assert cols["parent_llm_invoke_id"] == "VARCHAR"


class TestDuckdbColumnsUnknownNamespace:
    def test_returns_empty_dict(self):
        assert duckdb_columns("nope") == {}
