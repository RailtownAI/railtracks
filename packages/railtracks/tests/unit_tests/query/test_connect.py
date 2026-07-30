"""Tests for railtracks.query.connect — DuckDB views + EventQuery."""

from __future__ import annotations

import json
from contextlib import closing
from pathlib import Path

import pytest

pytest.importorskip("duckdb")

from railtracks.query import connect

from ._events import CUSTOM_NS_EVENT, LLM_CALL, NODE_START


def _write(path: Path, events: list[dict]) -> None:
    path.write_text("\n".join(json.dumps(e) for e in events) + "\n", encoding="utf-8")


def _tables(con) -> set[str]:
    return {row[0] for row in con.execute("SHOW TABLES").fetchall()}


def _columns(con, table: str) -> set[str]:
    return {row[0] for row in con.execute(f"DESCRIBE {table}").fetchall()}


class TestConnectSingleFile:
    def test_registers_requested_namespaces(self, tmp_path: Path):
        f = tmp_path / "e.jsonl"
        _write(f, [NODE_START, LLM_CALL])
        with closing(connect(f, ["node", "llm"])) as q:
            assert set(q.namespaces) == {"node", "llm"}
            assert q.namespaces_missing == []
            assert {"events", "node", "llm"} <= _tables(q.con)

    def test_returns_real_row_counts(self, tmp_path: Path):
        f = tmp_path / "e.jsonl"
        _write(f, [NODE_START, LLM_CALL])
        with closing(connect(f, ["llm"])) as q:
            (n,) = q.con.execute("SELECT COUNT(*) FROM llm").fetchone()
            assert n == 1


class TestConnectDirectory:
    def test_unions_all_jsonl_in_directory(self, tmp_path: Path):
        _write(tmp_path / "a.jsonl", [NODE_START])
        _write(tmp_path / "b.jsonl", [LLM_CALL])
        with closing(connect(tmp_path, ["node", "llm"])) as q:
            (nodes,) = q.con.execute("SELECT COUNT(*) FROM node").fetchone()
            (llms,) = q.con.execute("SELECT COUNT(*) FROM llm").fetchone()
            assert (nodes, llms) == (1, 1)


class TestSamples:
    def test_sampled_namespace_with_no_real_data_view_exists_zero_rows(self, tmp_path: Path):
        f = tmp_path / "e.jsonl"
        _write(f, [LLM_CALL])
        with closing(connect(f, ["node", "llm"])) as q:
            assert "node" in q.namespaces
            assert q.namespaces_missing == []
            (n,) = q.con.execute("SELECT COUNT(*) FROM node").fetchone()
            assert n == 0

    def test_sample_rows_never_leak_into_namespace_view(self, tmp_path: Path):
        f = tmp_path / "e.jsonl"
        _write(f, [LLM_CALL])
        with closing(connect(f, ["llm"])) as q:
            rows = q.con.execute("SELECT event_id FROM llm ORDER BY event_id").fetchall()
            assert rows == [("evt_llm_1",)]

    def test_events_view_excludes_samples(self, tmp_path: Path):
        f = tmp_path / "e.jsonl"
        _write(f, [LLM_CALL])
        with closing(connect(f, [])) as q:
            ids = [r[0] for r in q.con.execute("SELECT event_id FROM events").fetchall()]
            assert ids == ["evt_llm_1"]


class TestUnsampledNamespaces:
    def test_absent_from_data_lands_in_missing(self, tmp_path: Path):
        f = tmp_path / "e.jsonl"
        _write(f, [LLM_CALL])
        with closing(connect(f, ["retrieval"])) as q:
            assert q.namespaces == []
            assert q.namespaces_missing == ["retrieval"]

    def test_present_in_data_gets_registered(self, tmp_path: Path):
        f = tmp_path / "e.jsonl"
        _write(f, [CUSTOM_NS_EVENT])
        with closing(connect(f, ["custom"])) as q:
            assert q.namespaces == ["custom"]
            assert q.namespaces_missing == []
            (foo,) = q.con.execute("SELECT foo FROM custom").fetchone()
            assert foo == "bar"


class TestRefresh:
    def test_picks_up_namespace_that_appears_after_connect(self, tmp_path: Path):
        f = tmp_path / "e.jsonl"
        _write(f, [LLM_CALL])
        with closing(connect(f, ["llm", "retrieval"])) as q:
            assert q.namespaces_missing == ["retrieval"]
            new_event = {
                **CUSTOM_NS_EVENT,
                "event_id": "evt_r1",
                "event_type": "retrieval.query",
                "payload": {"query": "hi"},
            }
            with f.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(new_event) + "\n")
            q.refresh()
            assert "retrieval" in q.namespaces
            assert q.namespaces_missing == []
            (n,) = q.con.execute("SELECT COUNT(*) FROM retrieval").fetchone()
            assert n == 1

    def test_returns_none(self, tmp_path: Path):
        f = tmp_path / "e.jsonl"
        _write(f, [LLM_CALL])
        with closing(connect(f, ["llm"])) as q:
            assert q.refresh() is None


class TestEmptyNamespaces:
    def test_only_events_view_registered(self, tmp_path: Path):
        f = tmp_path / "e.jsonl"
        _write(f, [LLM_CALL])
        with closing(connect(f, [])) as q:
            assert q.namespaces == []
            assert q.namespaces_missing == []
            assert _tables(q.con) == {"events"}


class TestPayloadColumnBehavior:
    def test_scalar_payload_comes_back_as_varchar(self, tmp_path: Path):
        f = tmp_path / "e.jsonl"
        _write(f, [LLM_CALL])
        with closing(connect(f, ["llm"])) as q:
            row = q.con.execute("SELECT model, input_tokens FROM llm").fetchone()
            assert row == ("claude-opus-4-7", "812")

    def test_scalar_castable_to_bigint_for_math(self, tmp_path: Path):
        f = tmp_path / "e.jsonl"
        _write(f, [LLM_CALL])
        with closing(connect(f, ["llm"])) as q:
            (total,) = q.con.execute(
                "SELECT SUM(CAST(input_tokens AS BIGINT)) FROM llm"
            ).fetchone()
            assert total == 812

    def test_nested_payload_castable_to_json(self, tmp_path: Path):
        f = tmp_path / "e.jsonl"
        _write(f, [CUSTOM_NS_EVENT])
        with closing(connect(f, ["custom"])) as q:
            (n,) = q.con.execute(
                "SELECT json_array_length(CAST(children AS JSON)) FROM custom"
            ).fetchone()
            assert n == 1


class TestEnvelopeCollision:
    def test_payload_key_colliding_with_envelope_is_dropped(self, tmp_path: Path):
        # A rogue payload key `event_id` should not overwrite the envelope column.
        weird = {
            **NODE_START,
            "event_id": "evt_weird",
            "payload": {"event_id": "PAYLOAD_INSIDE", "node_id": "n1"},
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
        _write(f, [LLM_CALL])
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
