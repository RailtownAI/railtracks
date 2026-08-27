"""Tests for railtracks.query.connect — DuckDB views + EventQuery."""

from __future__ import annotations

import json
from contextlib import closing
from pathlib import Path

import pytest

pytest.importorskip("duckdb")

from railtracks.query import connect

from ._events import (
    CUSTOM_NS_EVENT,
    LLM_CREATION,
    LLM_RESPONSE,
    NODE_CREATION,
    SESSION_STARTED,
)


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
    def test_registered_namespace_with_no_events_still_gets_a_view(
        self, tmp_path: Path
    ):
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
            ids = [
                r[0] for r in q.con.execute("SELECT event_id FROM events").fetchall()
            ]
            assert ids == ["evt_llm_1"]

    def test_empty_jsonl_file_produces_an_empty_view(self, tmp_path: Path):
        f = tmp_path / "empty.jsonl"
        f.touch()

        with closing(connect(f, ["llm"])) as q:
            (event_count,) = q.con.execute("SELECT COUNT(*) FROM events").fetchone()
            (llm_count,) = q.con.execute("SELECT COUNT(*) FROM llm").fetchone()

        assert (event_count, llm_count) == (0, 0)

    def test_ignores_a_partial_final_line(self, tmp_path: Path):
        f = tmp_path / "e.jsonl"
        f.write_text(json.dumps(LLM_RESPONSE) + '\n{"event_id":', encoding="utf-8")

        with closing(connect(f, ["llm"])) as q:
            rows = q.con.execute("SELECT event_id FROM events").fetchall()

        assert rows == [("evt_llm_1",)]

    def test_ignores_a_malformed_line_and_reads_the_following_event(
        self, tmp_path: Path
    ):
        second = {**LLM_RESPONSE, "event_id": "evt_llm_2"}
        f = tmp_path / "e.jsonl"
        f.write_text(
            json.dumps(LLM_RESPONSE) + "\n{not-json}\n" + json.dumps(second) + "\n",
            encoding="utf-8",
        )

        with closing(connect(f, ["llm"])) as q:
            rows = q.con.execute(
                "SELECT event_id FROM events ORDER BY event_id"
            ).fetchall()

        assert rows == [("evt_llm_1",), ("evt_llm_2",)]

    @pytest.mark.parametrize(
        "missing",
        ("event_id", "event_type", "scope_type", "scope_id", "stamp", "payload"),
    )
    def test_rejects_incomplete_event_envelopes(self, tmp_path: Path, missing: str):
        incomplete = {
            key: value for key, value in LLM_RESPONSE.items() if key != missing
        }
        f = tmp_path / "e.jsonl"
        _write(f, [LLM_RESPONSE, incomplete])

        with closing(connect(f, ["llm"])) as q:
            (count,) = q.con.execute("SELECT COUNT(*) FROM events").fetchone()

        assert count == 1

    @pytest.mark.parametrize(
        "payload", (None, "not-an-object", ["not", "an", "object"])
    )
    def test_rejects_non_object_payloads(self, tmp_path: Path, payload):
        invalid = {**LLM_RESPONSE, "event_id": "evt_invalid", "payload": payload}
        f = tmp_path / "e.jsonl"
        _write(f, [LLM_RESPONSE, invalid])

        with closing(connect(f, ["llm"])) as q:
            event_ids = q.con.execute("SELECT event_id FROM events").fetchall()

        assert event_ids == [("evt_llm_1",)]


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
        # `output` is JSON in the registry; make sure we get JSON back.
        f = tmp_path / "e.jsonl"
        _write(f, [LLM_RESPONSE])
        with closing(connect(f, ["llm"])) as q:
            (output_type,) = q.con.execute("SELECT typeof(output) FROM llm").fetchone()
            assert output_type == "JSON"


class TestDiscriminatorColumns:
    def test_discriminator_column_lands_in_the_view_as_varchar(self, tmp_path: Path):
        f = tmp_path / "e.jsonl"
        _write(f, [LLM_RESPONSE])
        with closing(connect(f, ["llm"])) as q:
            (col_type,) = q.con.execute(
                "SELECT typeof(spatial_parent_type) FROM llm LIMIT 1"
            ).fetchone()
            assert col_type == "VARCHAR"

    def test_enum_value_readable_from_a_flat_column(self, tmp_path: Path):
        f = tmp_path / "e.jsonl"
        _write(f, [LLM_RESPONSE])
        with closing(connect(f, ["llm"])) as q:
            (value,) = q.con.execute(
                "SELECT spatial_parent_type FROM llm LIMIT 1"
            ).fetchone()
            assert value == "node"

    def test_unknown_discriminator_value_is_preserved(self, tmp_path: Path):
        # Older/newer values remain inspectable even when this build does not know
        # their semantics yet.
        stale = {
            **LLM_RESPONSE,
            "event_id": "evt_stale",
            "payload": {
                **LLM_RESPONSE["payload"],
                "spatial_parent_type": "some_future_kind",
            },
        }
        f = tmp_path / "e.jsonl"
        _write(f, [LLM_RESPONSE, stale])
        with closing(connect(f, ["llm"])) as q:
            rows = q.con.execute(
                "SELECT event_id, spatial_parent_type FROM llm ORDER BY event_id"
            ).fetchall()
            assert rows == [
                ("evt_llm_1", "node"),
                ("evt_stale", "some_future_kind"),
            ]


class TestSchemaEvolution:
    def test_incompatible_optional_scalars_become_null(self, tmp_path: Path):
        stale = {
            **LLM_RESPONSE,
            "event_id": "evt_stale",
            "payload": {
                **LLM_RESPONSE["payload"],
                "input_tokens": "not-an-integer",
                "latency": "not-a-float",
                "timestamp": "not-a-timestamp",
            },
        }
        f = tmp_path / "e.jsonl"
        _write(f, [LLM_RESPONSE, stale])

        with closing(connect(f, ["llm"])) as q:
            rows = q.con.execute(
                "SELECT event_id, input_tokens, latency, timestamp "
                "FROM llm ORDER BY event_id"
            ).fetchall()

        event_id, input_tokens, latency, timestamp = rows[0]
        assert (event_id, input_tokens, latency) == ("evt_llm_1", 812, 1.2)
        assert timestamp is not None
        assert rows[1] == ("evt_stale", None, None, None)

    def test_incompatible_optional_boolean_becomes_null(self, tmp_path: Path):
        stale = {
            **SESSION_STARTED,
            "event_id": "evt_stale",
            "payload": {
                **SESSION_STARTED["payload"],
                "end_on_error": "not-a-boolean",
            },
        }
        f = tmp_path / "e.jsonl"
        _write(f, [SESSION_STARTED, stale])

        with closing(connect(f, ["session"])) as q:
            rows = q.con.execute(
                "SELECT event_id, end_on_error FROM session ORDER BY event_id"
            ).fetchall()

        assert rows == [("evt_session_1", True), ("evt_stale", None)]

    def test_missing_and_unknown_payload_fields_do_not_break_mixed_files(
        self, tmp_path: Path
    ):
        old = {
            **LLM_RESPONSE,
            "event_id": "evt_old",
            "payload": {
                key: value
                for key, value in LLM_RESPONSE["payload"].items()
                if key != "input_tokens"
            },
        }
        new = {
            **LLM_RESPONSE,
            "event_id": "evt_new",
            "payload": {**LLM_RESPONSE["payload"], "future_field": {"v": 1}},
        }
        f = tmp_path / "e.jsonl"
        _write(f, [old, new])

        with closing(connect(f, ["llm"])) as q:
            typed = q.con.execute(
                "SELECT event_id, input_tokens FROM llm ORDER BY event_id"
            ).fetchall()
            raw = q.con.execute(
                "SELECT payload->'future_field' FROM events WHERE event_id = 'evt_new'"
            ).fetchone()

        assert typed == [("evt_new", 812), ("evt_old", None)]
        assert raw == ('{"v":1}',)


class TestFlatSpatialParent:
    def test_flat_spatial_parent_columns_returned_directly(self, tmp_path: Path):
        f = tmp_path / "e.jsonl"
        _write(f, [LLM_RESPONSE])
        with closing(connect(f, ["llm"])) as q:
            row = q.con.execute(
                "SELECT spatial_parent_type, spatial_parent_node_id FROM llm"
            ).fetchone()
            assert row == ("node", "node_root")


class TestFlatParent:
    def test_flat_parent_columns_returned_directly(self, tmp_path: Path):
        f = tmp_path / "e.jsonl"
        _write(f, [LLM_RESPONSE])
        with closing(connect(f, ["llm"])) as q:
            row = q.con.execute(
                "SELECT parent_type, parent_llm_type_id, parent_llm_invoke_id FROM llm"
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
