"""Tests for railtracks.query.read — file discovery + registry-backed namespace list."""

from __future__ import annotations

from pathlib import Path

from railtracks.query import list_namespaces
from railtracks.query.read import _resolve_data_files


class TestListNamespaces:
    def test_returns_the_registry_namespaces(self):
        # Registry-backed: always ["llm", "middleware", "node"] regardless of path.
        assert list_namespaces() == ["llm", "middleware", "node"]

    def test_path_argument_is_ignored(self, tmp_path: Path):
        assert list_namespaces(tmp_path) == ["llm", "middleware", "node"]
        assert list_namespaces(tmp_path / "does_not_exist") == [
            "llm",
            "middleware",
            "node",
        ]


class TestResolveDataFiles:
    def test_single_file(self, tmp_path: Path):
        f = tmp_path / "e.jsonl"
        f.write_text("", encoding="utf-8")
        assert _resolve_data_files(f) == [f]

    def test_directory_of_jsonl(self, tmp_path: Path):
        a = tmp_path / "a.jsonl"
        b = tmp_path / "b.jsonl"
        a.write_text("", encoding="utf-8")
        b.write_text("", encoding="utf-8")
        assert _resolve_data_files(tmp_path) == [a, b]

    def test_nonexistent_path_returns_empty(self, tmp_path: Path):
        assert _resolve_data_files(tmp_path / "nope") == []
