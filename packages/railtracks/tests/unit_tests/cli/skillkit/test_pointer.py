"""Tests for the pointer install and `railtracks skill show`."""

import sys
from pathlib import Path
from unittest.mock import patch

import pytest
from railtracks.cli import SKILL_REGISTRY, add_skill, main
from railtracks.cli._skillkit import (
    CLAUDE,
    install_skill_directory,
    load_skill,
    package_version,
    pointer_body,
)

SKILL_DIR = Path(".claude/skills/agent-builder")


@pytest.fixture(autouse=True)
def _in_tmp(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)


def test_installed_skill_md_points_at_skill_show():
    add_skill("claude:agent-builder")

    content = (SKILL_DIR / "SKILL.md").read_text(encoding="utf-8")
    assert "# Build a Railtracks Agent" in content
    assert "railtracks skill show agent-builder" in content
    assert "reference.md" in content
    assert "## Patterns to Follow" not in content


def test_claude_pointer_keeps_argument_placeholder():
    add_skill("claude:agent-builder")

    assert "$ARGUMENTS" in (SKILL_DIR / "SKILL.md").read_text(encoding="utf-8")


@pytest.mark.parametrize(
    "tool, root", [("codex", ".agents"), ("cursor", ".cursor"), ("copilot", ".github")]
)
def test_other_pointers_resolve_argument_placeholder(tool, root):
    add_skill(f"{tool}:agent-builder")

    content = Path(root, "skills/agent-builder/SKILL.md").read_text(encoding="utf-8")
    assert "$ARGUMENTS" not in content
    assert "railtracks skill show agent-builder" in content


def test_reference_holds_full_skill_stamped_with_version():
    add_skill("claude:agent-builder")

    reference = (SKILL_DIR / "reference.md").read_text(encoding="utf-8")
    assert reference.startswith(f"> Written for railtracks {package_version()}.")
    assert "## Patterns to Follow" in reference
    assert "$ARGUMENTS" not in reference


def test_skill_show_prints_full_skill_for_installed_version(capsys):
    with patch.object(sys, "argv", ["railtracks", "skill", "show", "agent-builder"]):
        main()

    out = capsys.readouterr().out
    assert out.startswith(f"> Instructions from railtracks {package_version()}")
    assert "## Patterns to Follow" in out
    assert "$ARGUMENTS" not in out


@pytest.mark.parametrize("name", sorted(SKILL_REGISTRY))
def test_skill_show_matches_every_bundled_skill(name, capsys):
    with patch.object(sys, "argv", ["railtracks", "skill", "show", name]):
        main()

    assert capsys.readouterr().out.strip()


@pytest.mark.parametrize(
    "args", [["skill"], ["skill", "list"], ["skill", "show"], ["skill", "show", "nope"]]
)
def test_skill_show_rejects_bad_usage(args):
    with patch.object(sys, "argv", ["railtracks", *args]):
        with pytest.raises(SystemExit) as exc:
            main()

    assert exc.value.code == 1


def test_generated_file_cannot_shadow_a_shipped_file(tmp_path):
    directory = tmp_path / "src" / "fixture-skill"
    directory.mkdir(parents=True)
    (directory / "SKILL.md").write_text(
        "---\nname: fixture-skill\ndescription: A fixture.\n---\n\n# Heading\n",
        encoding="utf-8",
    )
    (directory / "reference.md").write_text("# Shipped\n", encoding="utf-8")
    skill = load_skill(directory)

    with pytest.raises(ValueError, match="reference.md"):
        install_skill_directory(skill, CLAUDE, generated={"reference.md": "x"})


def test_plugin_pointer_installs_railtracks_instead_of_a_reference():
    body = pointer_body(SKILL_REGISTRY["agent-builder"], None)

    assert "railtracks skill show agent-builder" in body
    assert "pip install railtracks" in body
    assert "reference.md" not in body
