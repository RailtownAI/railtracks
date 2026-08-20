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


class TestDuckdbDiscriminatorColumns:
    def test_known_enum_values_are_stored_as_varchar(self):
        # The registry retains the known members, but physical DuckDB ENUMs would
        # turn values from a newer or older event stream into NULL.
        assert duckdb_columns("llm")["spatial_parent_type"] == "VARCHAR"
        assert duckdb_columns("llm")["parent_type"] == "VARCHAR"
        assert duckdb_columns("llm")["model_provider"] == "VARCHAR"
        assert duckdb_columns("session")["status"] == "VARCHAR"


class TestDuckdbColumnsUnknownNamespace:
    def test_returns_empty_dict(self):
        assert duckdb_columns("nope") == {}
