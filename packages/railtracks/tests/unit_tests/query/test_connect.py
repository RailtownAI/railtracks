"""Tests for railtracks.query.connect — DuckDB views + EventQuery."""

from __future__ import annotations

import json
from contextlib import closing
from pathlib import Path

import pytest

pytest.importorskip("duckdb")

from railtracks.query import connect

from ._events import CUSTOM_NS_EVENT, LLM_CREATION, LLM_RESPONSE, NODE_CREATION


def _write(path: Path, events: list[dict]) -> None:
    path.write_text("\n".join(json.dumps(e) for e in events) + "\n", encoding="utf-8")


def _tables(con) -> set[str]:
    return {row[0] for row in con.execute("SHOW TABLES").fetchall()}


def _columns(con, table: str) -> set[str]:
    return {row[0] for row in con.execute(f"DESCRIBE {table}").fetchall()}


class TestConnectSingleFile:
    def test_registers_requested_namespaces(self, tmp_path: Path):
        f = tmp_path / "e.jsonl"
        _write(f, [NODE_CREATION, LLM_RESPONSE])
        with closing(connect(f, ["node", "llm"])) as q:
            assert set(q.namespaces) == {"node", "llm"}
            assert {"events", "node", "llm"} <= _tables(q.con)

    def test_returns_real_row_counts(self, tmp_path: Path):
        f = tmp_path / "e.jsonl"
        _write(f, [NODE_CREATION, LLM_RESPONSE])
        with closing(connect(f, ["llm"])) as q:
            (n,) = q.con.execute("SELECT COUNT(*) FROM llm").fetchone()
            assert n == 1


class TestConnectDirectory:
    def test_unions_all_jsonl_in_directory(self, tmp_path: Path):
        _write(tmp_path / "a.jsonl", [NODE_CREATION])
        _write(tmp_path / "b.jsonl", [LLM_RESPONSE])
        with closing(connect(tmp_path, ["node", "llm"])) as q:
            (nodes,) = q.con.execute("SELECT COUNT(*) FROM node").fetchone()
            (llms,) = q.con.execute("SELECT COUNT(*) FROM llm").fetchone()
            assert (nodes, llms) == (1, 1)


class TestEmptyRegisteredNamespace:
    def test_registered_namespace_with_no_events_still_gets_a_view(self, tmp_path: Path):
        f = tmp_path / "e.jsonl"
        _write(f, [LLM_RESPONSE])
        with closing(connect(f, ["node", "llm"])) as q:
            assert set(q.namespaces) == {"node", "llm"}
            (n,) = q.con.execute("SELECT COUNT(*) FROM node").fetchone()
            assert n == 0


class TestEventsView:
    def test_events_view_contains_all_written_rows(self, tmp_path: Path):
        f = tmp_path / "e.jsonl"
        _write(f, [LLM_RESPONSE])
        with closing(connect(f, [])) as q:
            ids = [r[0] for r in q.con.execute("SELECT event_id FROM events").fetchall()]
            assert ids == ["evt_llm_1"]


class TestUnknownNamespace:
    def test_raises_valueerror_pointing_at_the_registry(self, tmp_path: Path):
        f = tmp_path / "e.jsonl"
        _write(f, [LLM_RESPONSE])
        with pytest.raises(ValueError) as exc:
            connect(f, ["retrieval"])
        msg = str(exc.value)
        assert "retrieval" in msg
        assert "NAMESPACE_COLUMNS" in msg
        assert "registry.py" in msg

    def test_lists_known_namespaces_in_the_message(self, tmp_path: Path):
        f = tmp_path / "e.jsonl"
        _write(f, [LLM_RESPONSE])
        with pytest.raises(ValueError) as exc:
            connect(f, ["retrieval"])
        msg = str(exc.value)
        for known in ("llm", "middleware", "node", "session"):
            assert known in msg

    def test_custom_events_in_data_do_not_auto_register(self, tmp_path: Path):
        # No scan-based fallback: only registry-known names are accepted.
        f = tmp_path / "e.jsonl"
        _write(f, [CUSTOM_NS_EVENT])
        with pytest.raises(ValueError, match="custom"):
            connect(f, ["custom"])


class TestRefresh:
    def test_picks_up_new_events_in_the_file(self, tmp_path: Path):
        f = tmp_path / "e.jsonl"
        _write(f, [LLM_RESPONSE])
        with closing(connect(f, ["llm"])) as q:
            (n,) = q.con.execute("SELECT COUNT(*) FROM llm").fetchone()
            assert n == 1
            new_event = {**LLM_RESPONSE, "event_id": "evt_llm_2"}
            with f.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(new_event) + "\n")
            q.refresh()
            (n,) = q.con.execute("SELECT COUNT(*) FROM llm").fetchone()
            assert n == 2

    def test_returns_none(self, tmp_path: Path):
        f = tmp_path / "e.jsonl"
        _write(f, [LLM_RESPONSE])
        with closing(connect(f, ["llm"])) as q:
            assert q.refresh() is None


class TestEmptyNamespaces:
    def test_only_events_view_registered(self, tmp_path: Path):
        f = tmp_path / "e.jsonl"
        _write(f, [LLM_RESPONSE])
        with closing(connect(f, [])) as q:
            assert q.namespaces == []
            assert _tables(q.con) == {"events"}


class TestTypedColumns:
    def test_integer_payload_comes_back_as_bigint(self, tmp_path: Path):
        f = tmp_path / "e.jsonl"
        _write(f, [LLM_RESPONSE])
        with closing(connect(f, ["llm"])) as q:
            (input_tokens,) = q.con.execute("SELECT input_tokens FROM llm").fetchone()
            assert input_tokens == 812
            assert isinstance(input_tokens, int)

    def test_float_payload_comes_back_as_double(self, tmp_path: Path):
        f = tmp_path / "e.jsonl"
        _write(f, [LLM_RESPONSE])
        with closing(connect(f, ["llm"])) as q:
            (latency,) = q.con.execute("SELECT latency FROM llm").fetchone()
            assert latency == 1.2
            assert isinstance(latency, float)

    def test_integer_sums_without_cast(self, tmp_path: Path):
        f = tmp_path / "e.jsonl"
        _write(f, [LLM_RESPONSE])
        with closing(connect(f, ["llm"])) as q:
            (total,) = q.con.execute("SELECT SUM(input_tokens) FROM llm").fetchone()
            assert total == 812

    def test_varchar_scalar_returns_unquoted_string(self, tmp_path: Path):
        f = tmp_path / "e.jsonl"
        _write(f, [LLM_CREATION])
        with closing(connect(f, ["llm"])) as q:
            (model_name,) = q.con.execute("SELECT model_name FROM llm").fetchone()
            assert model_name == "claude-opus-4-7"

    def test_json_column_stays_native_json(self, tmp_path: Path):
        # `model_provider` is JSON in the registry; make sure we get JSON back.
        f = tmp_path / "e.jsonl"
        _write(f, [LLM_CREATION])
        with closing(connect(f, ["llm"])) as q:
            (provider_type,) = q.con.execute(
                "SELECT typeof(model_provider) FROM llm"
            ).fetchone()
            assert provider_type == "JSON"


class TestEnumColumns:
    def test_discriminator_column_lands_in_the_view_as_a_duckdb_enum(self, tmp_path: Path):
        f = tmp_path / "e.jsonl"
        _write(f, [LLM_RESPONSE])
        with closing(connect(f, ["llm"])) as q:
            (col_type,) = q.con.execute(
                "SELECT typeof(spatial_parent_spatial_type) FROM llm LIMIT 1"
            ).fetchone()
            assert col_type.startswith("ENUM(")
            for member in ("'none'", "'node'", "'middleware'"):
                assert member in col_type

    def test_enum_value_readable_from_a_flat_column(self, tmp_path: Path):
        f = tmp_path / "e.jsonl"
        _write(f, [LLM_RESPONSE])
        with closing(connect(f, ["llm"])) as q:
            (value,) = q.con.execute(
                "SELECT spatial_parent_spatial_type FROM llm LIMIT 1"
            ).fetchone()
            assert value == "node"  # enum compares equal to its string value


class TestFlatSpatialParent:
    def test_flat_spatial_parent_columns_returned_directly(self, tmp_path: Path):
        f = tmp_path / "e.jsonl"
        _write(f, [LLM_RESPONSE])
        with closing(connect(f, ["llm"])) as q:
            row = q.con.execute(
                "SELECT spatial_parent_spatial_type, spatial_parent_node_id FROM llm"
            ).fetchone()
            assert row == ("node", "node_root")


class TestFlatParent:
    def test_flat_parent_columns_returned_directly(self, tmp_path: Path):
        f = tmp_path / "e.jsonl"
        _write(f, [LLM_RESPONSE])
        with closing(connect(f, ["llm"])) as q:
            row = q.con.execute(
                "SELECT parent_parent_type, parent_llm_type_id, parent_llm_invoke_id FROM llm"
            ).fetchone()
            assert row == ("llm", "llm_type_a", "llm_invoke_b")


class TestEnvelopeCollision:
    def test_payload_key_colliding_with_envelope_is_dropped(self, tmp_path: Path):
        # A rogue payload key `event_id` should not overwrite the envelope column.
        weird = {
            **NODE_CREATION,
            "event_id": "evt_weird",
            "payload": {**NODE_CREATION["payload"], "event_id": "PAYLOAD_INSIDE"},
        }
        f = tmp_path / "e.jsonl"
        _write(f, [weird])
        with closing(connect(f, ["node"])) as q:
            cols = _columns(q.con, "node")
            # `event_id` is present (as the envelope column) — not doubled.
            assert "event_id" in cols
            (event_id,) = q.con.execute("SELECT event_id FROM node").fetchone()
            assert event_id == "evt_weird"


class TestContextManager:
    def test_close_closes_the_connection(self, tmp_path: Path):
        f = tmp_path / "e.jsonl"
        _write(f, [LLM_RESPONSE])
        q = connect(f, ["llm"])
        with q:
            (n,) = q.con.execute("SELECT COUNT(*) FROM llm").fetchone()
            assert n == 1
        import duckdb

        with pytest.raises(duckdb.ConnectionException):
            q.con.execute("SELECT 1")


class TestDuckdbMissing:
    def test_raises_with_install_hint(self, tmp_path: Path, monkeypatch):
        import builtins

        real_import = builtins.__import__

        def fake_import(name, *args, **kwargs):
            if name == "duckdb":
                raise ImportError("no module named duckdb")
            return real_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", fake_import)

        with pytest.raises(ImportError, match=r"railtracks\[visual\]"):
            connect(tmp_path, [])
