"""Tests for `railtracks agents-md`, the managed Railtracks block in AGENTS.md."""

import inspect
import re
import sys
from unittest.mock import patch

import pytest
import railtracks as rt
from railtracks.cli import main
from railtracks.cli._agents_md import (
    BEGIN_MARKER,
    END_MARKER,
    TEMPLATE_PATH,
    FileChange,
    MalformedBlockError,
    render_block,
    upsert_block,
    write_agents_md,
)

# Claude Code advises < 200 lines per memory file; Vercel's winning index was ~8KB.
MAX_BLOCK_LINES = 120
MAX_BLOCK_BYTES = 8 * 1024


def _run_cli(*args: str) -> None:
    with patch.object(sys, "argv", ["railtracks", *args]):
        main()


class TestWriteAgentsMd:
    def test_creates_both_files(self, tmp_path):
        changes = write_agents_md(tmp_path, version="9.9.9")

        assert changes == [
            (tmp_path / "AGENTS.md", FileChange.CREATED),
            (tmp_path / "CLAUDE.md", FileChange.CREATED),
        ]
        assert (tmp_path / "AGENTS.md").read_text() == render_block("9.9.9")
        assert (tmp_path / "CLAUDE.md").read_text() == "@AGENTS.md\n"

    def test_rerun_changes_nothing(self, tmp_path):
        write_agents_md(tmp_path, version="9.9.9")
        before = {p: p.read_bytes() for p in tmp_path.iterdir()}

        changes = write_agents_md(tmp_path, version="9.9.9")

        assert [change for _, change in changes] == [FileChange.UNCHANGED] * 2
        assert {p: p.read_bytes() for p in tmp_path.iterdir()} == before

    def test_appends_block_to_existing_agents_md(self, tmp_path):
        (tmp_path / "AGENTS.md").write_text("# My project\n\nOur own rules.\n")

        changes = write_agents_md(tmp_path, version="9.9.9")

        assert changes[0][1] is FileChange.UPDATED
        assert (tmp_path / "AGENTS.md").read_text() == (
            "# My project\n\nOur own rules.\n\n" + render_block("9.9.9")
        )

    def test_updates_block_and_keeps_surrounding_content_byte_for_byte(self, tmp_path):
        before = "# Mine\r\nKeep this.\r\n\r\n"
        after = "\r\n## Also mine\r\nTrailing text without newline"
        stale = f"{BEGIN_MARKER}\nold rules\n{END_MARKER}\n"
        (tmp_path / "AGENTS.md").write_bytes((before + stale + after).encode())

        changes = write_agents_md(tmp_path, version="9.9.9")

        assert changes[0][1] is FileChange.UPDATED
        content = (tmp_path / "AGENTS.md").read_bytes().decode()
        assert content == before + render_block("9.9.9") + after
        assert content.count(BEGIN_MARKER) == 1

    def test_version_bump_replaces_only_the_block(self, tmp_path):
        (tmp_path / "AGENTS.md").write_text("# Mine\n")
        write_agents_md(tmp_path, version="1.0.0")

        write_agents_md(tmp_path, version="2.0.0")

        content = (tmp_path / "AGENTS.md").read_text()
        assert content == "# Mine\n\n" + render_block("2.0.0")
        assert "railtracks 1.0.0" not in content

    def test_ignores_markers_mentioned_in_prose(self, tmp_path):
        prose = f"The block sits between `{BEGIN_MARKER}` and `{END_MARKER}`.\n"
        (tmp_path / "AGENTS.md").write_text(prose)

        write_agents_md(tmp_path, version="9.9.9")

        assert (tmp_path / "AGENTS.md").read_text() == (
            prose + "\n" + render_block("9.9.9")
        )

    def test_adds_import_to_existing_claude_md(self, tmp_path):
        (tmp_path / "CLAUDE.md").write_text("# Notes\nUse tabs.")

        changes = write_agents_md(tmp_path)

        assert changes[1][1] is FileChange.UPDATED
        assert (tmp_path / "CLAUDE.md").read_text() == (
            "# Notes\nUse tabs.\n\n@AGENTS.md\n"
        )

    def test_leaves_claude_md_with_import_alone(self, tmp_path):
        original = b"# Notes\r\n  @AGENTS.md  \r\nMore notes"
        (tmp_path / "CLAUDE.md").write_bytes(original)

        changes = write_agents_md(tmp_path)

        assert changes[1][1] is FileChange.UNCHANGED
        assert (tmp_path / "CLAUDE.md").read_bytes() == original

    @pytest.mark.parametrize(
        "content",
        [
            f"{BEGIN_MARKER}\nno end\n",
            f"no begin\n{END_MARKER}\n",
            f"{END_MARKER}\n{BEGIN_MARKER}\n",
        ],
    )
    def test_refuses_unmatched_markers(self, content):
        with pytest.raises(MalformedBlockError):
            upsert_block(content, render_block("9.9.9"))


class TestCommand:
    def test_writes_files_in_cwd_and_reports_them(self, tmp_path, monkeypatch, capsys):
        monkeypatch.chdir(tmp_path)

        _run_cli("agents-md")

        assert (tmp_path / "AGENTS.md").exists()
        assert (tmp_path / "CLAUDE.md").exists()
        out = capsys.readouterr().out
        assert "Created AGENTS.md" in out
        assert "Created CLAUDE.md" in out

        _run_cli("agents-md")

        out = capsys.readouterr().out
        assert "Unchanged AGENTS.md" in out
        assert "Unchanged CLAUDE.md" in out

    def test_malformed_agents_md_exits_without_writing(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        broken = f"{BEGIN_MARKER}\nhalf a block\n"
        (tmp_path / "AGENTS.md").write_text(broken)

        with pytest.raises(SystemExit) as exc:
            _run_cli("agents-md")

        assert exc.value.code == 1
        assert (tmp_path / "AGENTS.md").read_text() == broken
        assert not (tmp_path / "CLAUDE.md").exists()


class TestBlockContent:
    def test_stays_within_budget(self):
        block = render_block()

        assert len(block.splitlines()) <= MAX_BLOCK_LINES
        assert len(block.encode("utf-8")) <= MAX_BLOCK_BYTES

    def test_is_stamped_with_version(self):
        assert "Written by railtracks 9.9.9;" in render_block("9.9.9")
        assert "{railtracks_version}" not in render_block()

    def test_code_example_runs(self):
        """The example must build real agents, so it can't drift from the API."""
        text = TEMPLATE_PATH.read_text(encoding="utf-8")
        code = re.search(r"```python\n(.*?)```", text, re.DOTALL).group(1)
        namespace = {"__name__": "agents_md_example"}

        exec(compile(code, str(TEMPLATE_PATH), "exec"), namespace)

        assert isinstance(namespace["flow"], rt.Flow)

    @pytest.mark.parametrize(
        ("target", "keywords"),
        [
            (
                rt.agent_node,
                [
                    "llm",
                    "tool_nodes",
                    "output_schema",
                    "system_message",
                    "manifest",
                    "middleware",
                    "model_middleware",
                ],
            ),
            (rt.Flow, ["name", "entry_point"]),
            (rt.ToolManifest, ["description", "parameters"]),
        ],
    )
    def test_keyword_arguments_exist(self, target, keywords):
        text = TEMPLATE_PATH.read_text(encoding="utf-8")
        params = inspect.signature(target).parameters

        for keyword in keywords:
            assert f"{keyword}=" in text
            assert keyword in params
