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
    def test_spatial_parent_id_subfields_stay_varchar(self):
        cols = duckdb_columns("llm")
        assert cols["spatial_parent_node_id"] == "VARCHAR"
        assert cols["spatial_parent_middleware_invoke_id"] == "VARCHAR"

    def test_parent_id_subfields_stay_varchar(self):
        cols = duckdb_columns("llm")
        assert cols["parent_node_id"] == "VARCHAR"
        assert cols["parent_llm_invoke_id"] == "VARCHAR"


class TestDuckdbEnumColumns:
    def test_spatial_type_discriminator_is_enum(self):
        col = duckdb_columns("llm")["spatial_parent_type"]
        assert col.startswith("ENUM(")
        # Every SpatialParent subclass value must be represented.
        for member in ("'none'", "'node'", "'middleware'", "'node_and_middleware'", "'llm_and_middleware'"):
            assert member in col

    def test_parent_type_discriminator_is_enum(self):
        col = duckdb_columns("llm")["parent_type"]
        assert col.startswith("ENUM(")
        for member in ("'node'", "'middleware'", "'llm'"):
            assert member in col

    def test_bare_string_literal_becomes_enum(self):
        # SessionCompleted.status: Literal["success", "failure"]
        col = duckdb_columns("session")["status"]
        assert col.startswith("ENUM(")
        for member in ("'success'", "'failure'"):
            assert member in col


class TestDuckdbColumnsUnknownNamespace:
    def test_returns_empty_dict(self):
        assert duckdb_columns("nope") == {}
