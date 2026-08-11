"""Tests for railtracks.query.read — file discovery, plus the registry reexport."""

from __future__ import annotations

from pathlib import Path

from railtracks.query import list_namespaces
from railtracks.query.read import resolve_data_files


class TestListNamespaces:
    def test_returns_the_registry_namespaces(self):
        assert list_namespaces() == ["llm", "middleware", "node", "session"]


class TestResolveDataFiles:
    def test_single_file(self, tmp_path: Path):
        f = tmp_path / "e.jsonl"
        f.write_text("", encoding="utf-8")
        assert resolve_data_files(f) == [f]

    def test_directory_of_jsonl(self, tmp_path: Path):
        a = tmp_path / "a.jsonl"
        b = tmp_path / "b.jsonl"
        a.write_text("", encoding="utf-8")
        b.write_text("", encoding="utf-8")
        assert resolve_data_files(tmp_path) == [a, b]

    def test_nonexistent_path_returns_empty(self, tmp_path: Path):
        assert resolve_data_files(tmp_path / "nope") == []
