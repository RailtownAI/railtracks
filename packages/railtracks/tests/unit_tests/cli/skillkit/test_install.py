#!/usr/bin/env python3

"""Tests for `_skillkit.install`: the directory copy, and the sync built on it."""

import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import yaml
from railtracks.cli import (
    _add_claude,
    _strip_skill_arguments,
    add_skill,
)
from railtracks.cli._skillkit.install import (
    CLAUDE,
    InstallTarget,
    install_skill_directory,
)
from railtracks.cli._skillkit.manifest import (
    MANIFEST_FILE,
    package_version,
    read_record,
)
from railtracks.cli._skillkit.registry import load_skill


def _write_skill(root, name, frontmatter, body="# Heading\n\nBody text.\n", files=None):
    """Create a synthetic skill directory and return the loaded `Skill`.

    Bundled skills deliberately ship no supporting files and no `tools:` block —
    `test_registry` asserts both, as the canary for when content work starts —
    so the directory install can only be exercised against fixtures until then.
    """
    directory = Path(root) / name
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "SKILL.md").write_text(
        f"---\n{frontmatter}---\n\n{body}", encoding="utf-8"
    )
    for relative, content in (files or {}).items():
        path = directory / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    return load_skill(directory)


class TestClaudeDirectoryInstall(unittest.TestCase):
    """`railtracks add claude:<skill>` copies a skill directory, not a flat file."""

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.source = Path(tempfile.mkdtemp())
        self.original_cwd = os.getcwd()
        os.chdir(self.test_dir)

    def tearDown(self):
        os.chdir(self.original_cwd)
        shutil.rmtree(self.test_dir)
        shutil.rmtree(self.source)

    def _installed(self, name="fixture-skill"):
        return Path(f".claude/skills/{name}/SKILL.md").read_text(encoding="utf-8")

    def test_supporting_files_keep_their_relative_subpaths(self):
        """A `references/` tree is what the directory install exists to carry."""
        skill = _write_skill(
            self.source,
            "fixture-skill",
            "name: fixture-skill\ndescription: A fixture.\n",
            files={
                "references/api.md": "# Generated API\n",
                "references/nested/data.json": '{"k": 1}\n',
                "scripts/demo.py": "print('hi')\n",
            },
        )

        _add_claude(skill, force=False)

        root = Path(".claude/skills/fixture-skill")
        self.assertEqual(
            (root / "references/api.md").read_text(encoding="utf-8"),
            "# Generated API\n",
        )
        self.assertEqual(
            (root / "references/nested/data.json").read_text(encoding="utf-8"),
            '{"k": 1}\n',
        )
        self.assertEqual(
            (root / "scripts/demo.py").read_text(encoding="utf-8"), "print('hi')\n"
        )

    def test_skill_without_supporting_files_is_unchanged(self):
        """The flat-file output this replaced must survive byte for byte."""
        skill = _write_skill(
            self.source,
            "fixture-skill",
            'name: fixture-skill\ndescription: A fixture.\nargument-hint: "[what to do]"\n',
        )

        _add_claude(skill, force=False)

        self.assertEqual(
            self._installed(),
            "---\nname: fixture-skill\ndescription: A fixture.\n"
            'argument-hint: "[what to do]"\n---\n\n# Heading\n\nBody text.\n',
        )

    def test_absent_argument_hint_omits_the_key(self):
        """An optional key with no value must not ship as the literal "None"."""
        skill = _write_skill(
            self.source, "fixture-skill", "name: fixture-skill\ndescription: A fixture.\n"
        )

        _add_claude(skill, force=False)

        content = self._installed()
        self.assertNotIn("argument-hint", content)
        self.assertNotIn("None", content)

    def test_tools_claude_block_is_merged_into_the_frontmatter(self):
        """Including keys this version has never heard of — they are forward support."""
        skill = _write_skill(
            self.source,
            "fixture-skill",
            "name: fixture-skill\ndescription: A fixture.\n"
            "tools:\n"
            "  claude:\n"
            "    allowed-tools: [Read, Edit]\n"
            "    disable-model-invocation: true\n"
            "    some-future-key: yes-please\n",
        )

        _add_claude(skill, force=False)

        frontmatter = yaml.safe_load(self._installed().split("---\n")[1])
        self.assertEqual(frontmatter["allowed-tools"], ["Read", "Edit"])
        self.assertIs(frontmatter["disable-model-invocation"], True)
        self.assertEqual(frontmatter["some-future-key"], "yes-please")
        self.assertEqual(frontmatter["name"], "fixture-skill")

    def test_other_assistants_tool_blocks_are_not_emitted(self):
        """`tools.cursor` is Cursor's projection to make, not Claude's."""
        skill = _write_skill(
            self.source,
            "fixture-skill",
            "name: fixture-skill\ndescription: A fixture.\n"
            "tools:\n"
            "  cursor:\n"
            "    globs: '**/*.py'\n",
        )

        _add_claude(skill, force=False)

        self.assertNotIn("globs", self._installed())

    def test_skill_keys_win_over_a_colliding_tools_key(self):
        """A duplicate frontmatter key is resolved silently by the reader; warn instead."""
        skill = _write_skill(
            self.source,
            "fixture-skill",
            "name: fixture-skill\ndescription: A fixture.\n"
            "tools:\n"
            "  claude:\n"
            "    description: Sneaky override.\n",
        )

        with patch("railtracks.cli._skillkit.install.print_warning") as mock_warning:
            _add_claude(skill, force=False)

        frontmatter = yaml.safe_load(self._installed().split("---\n")[1])
        self.assertEqual(frontmatter["description"], "A fixture.")
        mock_warning.assert_called_once()

    def test_force_overwrites_an_existing_directory_without_prompting(self):
        """`--force` covers the directory case, not just the single file."""
        skill = _write_skill(
            self.source,
            "fixture-skill",
            "name: fixture-skill\ndescription: A fixture.\n",
            files={"references/api.md": "# Second\n"},
        )
        target = Path(".claude/skills/fixture-skill/references")
        target.mkdir(parents=True)
        (target / "api.md").write_text("# First\n", encoding="utf-8")

        with patch("builtins.input", side_effect=AssertionError("prompted anyway")):
            _add_claude(skill, force=True)

        self.assertEqual((target / "api.md").read_text(encoding="utf-8"), "# Second\n")

    def test_declining_the_prompt_writes_nothing(self):
        """A refused overwrite must leave every file it would have touched alone."""
        skill = _write_skill(
            self.source,
            "fixture-skill",
            "name: fixture-skill\ndescription: A fixture.\n",
            files={"references/api.md": "# Second\n"},
        )
        target = Path(".claude/skills/fixture-skill/references")
        target.mkdir(parents=True)
        (target / "api.md").write_text("# First\n", encoding="utf-8")

        with patch("builtins.input", return_value="n"):
            with self.assertRaises(SystemExit):
                _add_claude(skill, force=False)

        self.assertEqual((target / "api.md").read_text(encoding="utf-8"), "# First\n")
        self.assertFalse(Path(".claude/skills/fixture-skill/SKILL.md").exists())

    def test_returns_every_file_it_wrote(self):
        """The install manifest's input; deriving it a second time would drift."""
        skill = _write_skill(
            self.source,
            "fixture-skill",
            "name: fixture-skill\ndescription: A fixture.\n",
            files={"references/api.md": "# Generated\n", "scripts/demo.py": "x = 1\n"},
        )

        written = _add_claude(skill, force=False)

        self.assertEqual(
            written,
            [
                Path(".claude/skills/fixture-skill/SKILL.md"),
                Path(".claude/skills/fixture-skill/references/api.md"),
                Path(".claude/skills/fixture-skill/scripts/demo.py"),
            ],
        )
        self.assertTrue(all(path.is_file() for path in written))

    def test_add_skill_reports_the_files_written(self):
        """The list has to survive the CLI entry point, not just the handler."""
        written = add_skill("claude:agent-builder")

        self.assertEqual(
            written, [Path(".claude/skills/agent-builder/SKILL.md")]
        )

    def test_a_dropped_supporting_file_is_removed(self):
        """The hazard #1522 exists to close: a slimmed-down skill leaves no leftovers.

        Replaces `test_a_dropped_supporting_file_is_left_behind`, which pinned the
        pre-manifest behaviour.
        """
        first = _write_skill(
            self.source,
            "fixture-skill",
            "name: fixture-skill\ndescription: A fixture.\n",
            files={"references/gone.md": "# Shipped once\n"},
        )
        _add_claude(first, force=True)
        (first.directory / "references/gone.md").unlink()

        _add_claude(load_skill(first.directory), force=True)

        self.assertFalse(Path(".claude/skills/fixture-skill/references/gone.md").exists())
        # The directory it emptied goes too, rather than lingering as a husk.
        self.assertFalse(Path(".claude/skills/fixture-skill/references").exists())
        self.assertTrue(Path(".claude/skills/fixture-skill/SKILL.md").is_file())


class TestSkillSync(unittest.TestCase):
    """Re-installing is a sync: it records what it wrote and removes what it dropped."""

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.source = Path(tempfile.mkdtemp())
        self.original_cwd = os.getcwd()
        os.chdir(self.test_dir)

    def tearDown(self):
        os.chdir(self.original_cwd)
        shutil.rmtree(self.test_dir)
        shutil.rmtree(self.source)

    def _fixture(self, files=None):
        return _write_skill(
            self.source,
            "fixture-skill",
            "name: fixture-skill\ndescription: A fixture.\n",
            files=files,
        )

    @property
    def _manifest_path(self):
        return Path(".claude/skills/fixture-skill") / MANIFEST_FILE

    def test_install_writes_a_manifest_beside_the_skill(self):
        """The record lives with the files, so it cannot outlive them."""
        _add_claude(self._fixture({"references/api.md": "# Generated\n"}), force=False)

        record = read_record(Path(".claude/skills/fixture-skill"))
        self.assertEqual(record.skill, "fixture-skill")
        self.assertEqual(record.target, "claude")
        self.assertEqual(
            {f.path for f in record.files}, {"SKILL.md", "references/api.md"}
        )

    def test_the_manifest_is_not_reported_as_an_installed_file(self):
        """It describes the install; it is not part of it."""
        written = _add_claude(self._fixture(), force=False)

        self.assertNotIn(self._manifest_path, written)
        self.assertTrue(self._manifest_path.is_file())

    def test_reinstalling_an_unchanged_skill_does_not_prompt(self):
        """Nagging about our own untouched output only trains people to use --force."""
        skill = self._fixture({"references/api.md": "# Generated\n"})
        _add_claude(skill, force=False)

        with patch("builtins.input", side_effect=AssertionError("prompted anyway")):
            _add_claude(skill, force=False)

        self.assertTrue(Path(".claude/skills/fixture-skill/SKILL.md").is_file())

    def test_a_file_we_never_wrote_still_prompts(self):
        """Absence of a record is not evidence a file is ours to clobber."""
        skill = self._fixture()
        target = Path(".claude/skills/fixture-skill")
        target.mkdir(parents=True)
        (target / "SKILL.md").write_text("hand written\n", encoding="utf-8")

        with patch("builtins.input", return_value="n"):
            with self.assertRaises(SystemExit):
                _add_claude(skill, force=False)

        self.assertEqual(
            (target / "SKILL.md").read_text(encoding="utf-8"), "hand written\n"
        )

    def test_an_edited_installed_file_prompts_again(self):
        """Once the bytes move, we can no longer prove the file is ours."""
        skill = self._fixture()
        _add_claude(skill, force=False)
        Path(".claude/skills/fixture-skill/SKILL.md").write_text(
            "I changed this\n", encoding="utf-8"
        )

        with patch("builtins.input", return_value="n"):
            with self.assertRaises(SystemExit):
                _add_claude(skill, force=False)

    def test_an_edited_dropped_file_is_kept_and_reported(self):
        """A sync removes its own leftovers, not somebody else's work."""
        first = self._fixture({"references/gone.md": "# Shipped once\n"})
        _add_claude(first, force=True)
        Path(".claude/skills/fixture-skill/references/gone.md").write_text(
            "I rewrote this\n", encoding="utf-8"
        )
        (first.directory / "references/gone.md").unlink()

        with patch("railtracks.cli._skillkit.install.print_warning") as mock_warning:
            _add_claude(load_skill(first.directory), force=True)

        kept = Path(".claude/skills/fixture-skill/references/gone.md")
        self.assertTrue(kept.is_file())
        self.assertEqual(kept.read_text(encoding="utf-8"), "I rewrote this\n")
        mock_warning.assert_called_once()

    def test_the_manifest_tracks_a_shrinking_skill(self):
        """After a sync the record describes what is actually on disk."""
        first = self._fixture({"references/gone.md": "x\n", "references/stays.md": "y\n"})
        _add_claude(first, force=True)
        (first.directory / "references/gone.md").unlink()

        _add_claude(load_skill(first.directory), force=True)

        record = read_record(Path(".claude/skills/fixture-skill"))
        self.assertEqual(
            {f.path for f in record.files}, {"SKILL.md", "references/stays.md"}
        )

    def test_reinstalling_produces_an_identical_manifest(self):
        """A committed manifest must not churn the diff on every re-run."""
        skill = self._fixture({"references/api.md": "# Generated\n"})
        _add_claude(skill, force=True)
        first = self._manifest_path.read_text(encoding="utf-8")

        _add_claude(skill, force=True)

        self.assertEqual(self._manifest_path.read_text(encoding="utf-8"), first)

    def test_version_skew_is_reported(self):
        """Acceptance: a manifest from an older package version is detected."""
        skill = self._fixture()
        _add_claude(skill, force=True)
        stale = self._manifest_path.read_text(encoding="utf-8").replace(
            f'"package_version": "{package_version()}"', '"package_version": "0.0.1"'
        )
        self._manifest_path.write_text(stale, encoding="utf-8")

        with patch("railtracks.cli._skillkit.install.print_status") as mock_status:
            _add_claude(skill, force=True)

        reported = " ".join(str(c.args[0]) for c in mock_status.call_args_list if c.args)
        self.assertIn("0.0.1", reported)

    def test_a_bundled_skill_installs_and_records_itself(self):
        """The whole path, through the CLI entry point rather than the handler."""
        written = add_skill("claude:agent-builder")

        record = read_record(Path(".claude/skills/agent-builder"))
        self.assertEqual(record.skill, "agent-builder")
        self.assertEqual([f.path for f in record.files], ["SKILL.md"])
        self.assertEqual(written, [Path(".claude/skills/agent-builder/SKILL.md")])


class TestInstallTargetParameters(unittest.TestCase):
    """The two parameters are the deliverable: a target root, and a projection."""

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.source = Path(tempfile.mkdtemp())
        self.original_cwd = os.getcwd()
        os.chdir(self.test_dir)

    def tearDown(self):
        os.chdir(self.original_cwd)
        shutil.rmtree(self.test_dir)
        shutil.rmtree(self.source)

    def test_claude_target_writes_to_its_native_path(self):
        """Each assistant gets its own root, never a path it merely also reads."""
        self.assertEqual(CLAUDE.root, Path(".claude") / "skills")

    def test_another_target_needs_only_a_root_and_a_projection(self):
        """Stand up a second target with no new code; that is what makes it reusable."""
        skill = _write_skill(
            self.source,
            "fixture-skill",
            "name: fixture-skill\ndescription: A fixture.\n",
            body="Use $ARGUMENTS here.\n",
            files={"references/api.md": "# Generated\n"},
        )
        elsewhere = InstallTarget(
            key="somewhere",
            label="Some Assistant",
            root=Path(".somewhere") / "skills",
            frontmatter=lambda s: f"---\nname: {s.name}\n---\n\n",
            body=lambda s: _strip_skill_arguments(s.body),
        )

        written = install_skill_directory(skill, elsewhere)

        self.assertEqual(
            written,
            [
                Path(".somewhere/skills/fixture-skill/SKILL.md"),
                Path(".somewhere/skills/fixture-skill/references/api.md"),
            ],
        )
        content = written[0].read_text(encoding="utf-8")
        self.assertEqual(content, "---\nname: fixture-skill\n---\n\nUse the request here.")
        self.assertFalse(Path(".claude").exists())
