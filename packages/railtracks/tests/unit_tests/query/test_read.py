"""Tests for railtracks.query.read — file discovery + namespace scanning."""

from __future__ import annotations

import json
from pathlib import Path

from railtracks.query import list_namespaces

from ._events import CUSTOM_NS_EVENT, LLM_CALL


def _write(path: Path, events: list[dict]) -> None:
    path.write_text("\n".join(json.dumps(e) for e in events) + "\n", encoding="utf-8")


class TestListNamespaces:
    def test_union_of_samples_and_data(self, tmp_path: Path):
        f = tmp_path / "e.jsonl"
        _write(f, [LLM_CALL, CUSTOM_NS_EVENT])
        # samples floor: llm, middleware, node. data adds: llm (dup), custom.
        assert list_namespaces(f) == sorted({"llm", "middleware", "node", "custom"})

    def test_samples_alone_when_path_is_empty_directory(self, tmp_path: Path):
        # tmp_path has no jsonl files — only the bundled samples participate.
        assert list_namespaces(tmp_path) == sorted({"llm", "middleware", "node"})

    def test_samples_alone_when_path_does_not_exist(self, tmp_path: Path):
        assert list_namespaces(tmp_path / "does_not_exist") == sorted(
            {"llm", "middleware", "node"}
        )

    def test_single_file_path(self, tmp_path: Path):
        f = tmp_path / "e.jsonl"
        _write(f, [CUSTOM_NS_EVENT])
        assert "custom" in list_namespaces(f)

    def test_directory_unions_multiple_jsonl_files(self, tmp_path: Path):
        _write(tmp_path / "a.jsonl", [LLM_CALL])
        _write(tmp_path / "b.jsonl", [CUSTOM_NS_EVENT])
        assert {"llm", "custom"} <= set(list_namespaces(tmp_path))


class TestScanRobustness:
    def test_blank_lines_are_skipped(self, tmp_path: Path):
        (tmp_path / "e.jsonl").write_text(
            "\n" + json.dumps(CUSTOM_NS_EVENT) + "\n\n\n",
            encoding="utf-8",
        )
        assert "custom" in list_namespaces(tmp_path)

    def test_malformed_json_lines_are_skipped(self, tmp_path: Path):
        (tmp_path / "e.jsonl").write_text(
            json.dumps(LLM_CALL) + "\nnot valid json\n" + json.dumps(CUSTOM_NS_EVENT) + "\n",
            encoding="utf-8",
        )
        ns = list_namespaces(tmp_path)
        assert {"llm", "custom"} <= set(ns)

    def test_event_type_without_dot_is_skipped(self, tmp_path: Path):
        weird = {**LLM_CALL, "event_type": "no_dot_here"}
        (tmp_path / "e.jsonl").write_text(json.dumps(weird) + "\n", encoding="utf-8")
        ns = list_namespaces(tmp_path)
        # The un-namespaced event is ignored; only bundled samples count.
        assert "no_dot_here" not in ns
        assert ns == sorted({"llm", "middleware", "node"})

    def test_missing_event_type_is_skipped(self, tmp_path: Path):
        no_type = {k: v for k, v in LLM_CALL.items() if k != "event_type"}
        (tmp_path / "e.jsonl").write_text(json.dumps(no_type) + "\n", encoding="utf-8")
        ns = list_namespaces(tmp_path)
        assert ns == sorted({"llm", "middleware", "node"})

    def test_non_dict_payload_still_records_the_namespace(self, tmp_path: Path):
        # Payload is a list, not a dict — namespace should still be picked up,
        # but no payload keys contributed.
        weird = {**CUSTOM_NS_EVENT, "payload": [1, 2, 3]}
        (tmp_path / "e.jsonl").write_text(json.dumps(weird) + "\n", encoding="utf-8")
        assert "custom" in list_namespaces(tmp_path)


class TestSampleDiscovery:
    def test_bundled_samples_are_present(self):
        from railtracks.query.read import _sample_files

        names = [p.name for p in _sample_files()]
        assert set(names) == {"session.jsonl"}
