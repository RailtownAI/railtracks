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
    add_skill,
)
from railtracks.cli._skillkit import (
    CLAUDE,
    CODEX,
    COPILOT,
    CURSOR,
    MANIFEST_FILE,
    InstallTarget,
    install_skill_directory,
    load_skill,
    package_version,
    read_record,
    strip_skill_arguments,
)


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


class TestCodexDirectoryInstall(unittest.TestCase):
    """`railtracks add codex:<skill>` writes a skill directory under .agents/skills."""

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
        return Path(f".agents/skills/{name}/SKILL.md").read_text(encoding="utf-8")

    def test_codex_target_writes_to_its_native_path(self):
        """§3.1 / D8: Codex's native path is `.agents/skills/`."""
        self.assertEqual(CODEX.root, Path(".agents") / "skills")

    def test_argument_placeholder_is_stripped(self):
        """Codex documents no substitution, so `$ARGUMENTS` never survives (D9)."""
        skill = _write_skill(
            self.source,
            "fixture-skill",
            "name: fixture-skill\ndescription: A fixture.\n",
            body="Do the thing: $ARGUMENTS\n\nMore body.\n",
        )

        install_skill_directory(skill, CODEX)

        self.assertNotIn("$ARGUMENTS", self._installed())

    def test_argument_hint_is_dropped_from_the_frontmatter(self):
        """`argument-hint` is Claude-only; §3.5 keeps it off every other target."""
        skill = _write_skill(
            self.source,
            "fixture-skill",
            'name: fixture-skill\ndescription: A fixture.\nargument-hint: "[what]"\n',
        )

        install_skill_directory(skill, CODEX)

        self.assertNotIn("argument-hint", self._installed())

    def test_supporting_files_ride_along(self):
        """The whole point of the migration: `references/` travels with the skill."""
        skill = _write_skill(
            self.source,
            "fixture-skill",
            "name: fixture-skill\ndescription: A fixture.\n",
            files={"references/api.md": "# Generated\n"},
        )

        install_skill_directory(skill, CODEX)

        self.assertEqual(
            Path(".agents/skills/fixture-skill/references/api.md").read_text(
                encoding="utf-8"
            ),
            "# Generated\n",
        )

    def test_install_writes_a_manifest_beside_the_skill(self):
        """Codex now participates in sync semantics — the record makes it so."""
        skill = _write_skill(
            self.source,
            "fixture-skill",
            "name: fixture-skill\ndescription: A fixture.\n",
        )

        install_skill_directory(skill, CODEX)

        record = read_record(Path(".agents/skills/fixture-skill"))
        self.assertEqual(record.target, "codex")
        self.assertEqual([f.path for f in record.files], ["SKILL.md"])


class TestCopilotDirectoryInstall(unittest.TestCase):
    """`railtracks add copilot:<skill>` writes a skill directory under .github/skills."""

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
        return Path(f".github/skills/{name}/SKILL.md").read_text(encoding="utf-8")

    def test_copilot_target_writes_to_its_native_path(self):
        """§3.1 / D8: Copilot's native path is `.github/skills/`, not `.claude/skills`."""
        self.assertEqual(COPILOT.root, Path(".github") / "skills")

    def test_argument_placeholder_is_stripped(self):
        """Copilot documents no substitution, so `$ARGUMENTS` never survives (D9)."""
        skill = _write_skill(
            self.source,
            "fixture-skill",
            "name: fixture-skill\ndescription: A fixture.\n",
            body="Do the thing: $ARGUMENTS\n\nMore body.\n",
        )

        install_skill_directory(skill, COPILOT)

        self.assertNotIn("$ARGUMENTS", self._installed())

    def test_argument_hint_is_dropped_from_the_frontmatter(self):
        """`argument-hint` is Claude-only; §3.5 keeps it off every other target."""
        skill = _write_skill(
            self.source,
            "fixture-skill",
            'name: fixture-skill\ndescription: A fixture.\nargument-hint: "[what]"\n',
        )

        install_skill_directory(skill, COPILOT)

        self.assertNotIn("argument-hint", self._installed())

    def test_tools_copilot_block_is_merged_into_the_frontmatter(self):
        """`allowed-tools` and `license` from `tools.copilot` reach the target (§3.5)."""
        skill = _write_skill(
            self.source,
            "fixture-skill",
            "name: fixture-skill\ndescription: A fixture.\n"
            "tools:\n"
            "  copilot:\n"
            "    license: MIT\n"
            "    allowed-tools: [Read, Edit]\n",
        )

        install_skill_directory(skill, COPILOT)

        frontmatter = yaml.safe_load(self._installed().split("---\n")[1])
        self.assertEqual(frontmatter["license"], "MIT")
        self.assertEqual(frontmatter["allowed-tools"], ["Read", "Edit"])

    def test_other_assistants_tool_blocks_are_not_emitted(self):
        """`tools.claude` is Claude's projection to make, not Copilot's."""
        skill = _write_skill(
            self.source,
            "fixture-skill",
            "name: fixture-skill\ndescription: A fixture.\n"
            "tools:\n"
            "  claude:\n"
            "    allowed-tools: [Read]\n",
        )

        install_skill_directory(skill, COPILOT)

        content = self._installed()
        self.assertNotIn("Read", content)
        self.assertNotIn("allowed-tools", content)

    def test_supporting_files_ride_along(self):
        """The whole point of D8's directory install: `references/` travels with it."""
        skill = _write_skill(
            self.source,
            "fixture-skill",
            "name: fixture-skill\ndescription: A fixture.\n",
            files={"references/api.md": "# Generated\n"},
        )

        install_skill_directory(skill, COPILOT)

        self.assertEqual(
            Path(".github/skills/fixture-skill/references/api.md").read_text(
                encoding="utf-8"
            ),
            "# Generated\n",
        )


class TestCursorDirectoryInstall(unittest.TestCase):
    """`railtracks add cursor:<skill>` writes a skill directory under .cursor/skills."""

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
        return Path(f".cursor/skills/{name}/SKILL.md").read_text(encoding="utf-8")

    def test_cursor_target_writes_to_its_native_path(self):
        """§3.1 / D8: Cursor's native path is `.cursor/skills/`, not `.cursor/rules`."""
        self.assertEqual(CURSOR.root, Path(".cursor") / "skills")

    def test_argument_placeholder_is_stripped(self):
        """Cursor documents no substitution, so `$ARGUMENTS` never survives (D9)."""
        skill = _write_skill(
            self.source,
            "fixture-skill",
            "name: fixture-skill\ndescription: A fixture.\n",
            body="Do this: $ARGUMENTS\n\nMore body.\n",
        )

        install_skill_directory(skill, CURSOR)

        self.assertNotIn("$ARGUMENTS", self._installed())

    def test_frontmatter_name_equals_the_folder_name(self):
        """§3.1 requires `name == folder name`; the projection must preserve it."""
        skill = _write_skill(
            self.source,
            "fixture-skill",
            "name: fixture-skill\ndescription: A fixture.\n",
        )

        install_skill_directory(skill, CURSOR)

        frontmatter = yaml.safe_load(self._installed().split("---\n")[1])
        self.assertEqual(frontmatter["name"], "fixture-skill")
        # And the folder path derives from it, so the invariant is a real one.
        self.assertTrue(Path(".cursor/skills/fixture-skill").is_dir())

    def test_tools_cursor_block_is_merged_into_the_frontmatter(self):
        """`paths` and `disable-model-invocation` from `tools.cursor` reach it (§3.5)."""
        skill = _write_skill(
            self.source,
            "fixture-skill",
            "name: fixture-skill\ndescription: A fixture.\n"
            "tools:\n"
            "  cursor:\n"
            "    paths: '**/*.py'\n"
            "    disable-model-invocation: true\n",
        )

        install_skill_directory(skill, CURSOR)

        frontmatter = yaml.safe_load(self._installed().split("---\n")[1])
        self.assertEqual(frontmatter["paths"], "**/*.py")
        self.assertIs(frontmatter["disable-model-invocation"], True)

    def test_legacy_globs_is_normalised_to_paths(self):
        """§3.5: Cursor's docs renamed `globs` to `paths`; existing skills need no edit."""
        skill = _write_skill(
            self.source,
            "fixture-skill",
            "name: fixture-skill\ndescription: A fixture.\n"
            "tools:\n"
            "  cursor:\n"
            "    globs: '**/*.py'\n",
        )

        install_skill_directory(skill, CURSOR)

        frontmatter = yaml.safe_load(self._installed().split("---\n")[1])
        self.assertEqual(frontmatter["paths"], "**/*.py")
        self.assertNotIn("globs", frontmatter)

    def test_paths_wins_when_both_are_authored(self):
        """A skill written for the new key should not have it silently overwritten."""
        skill = _write_skill(
            self.source,
            "fixture-skill",
            "name: fixture-skill\ndescription: A fixture.\n"
            "tools:\n"
            "  cursor:\n"
            "    paths: '**/*.ts'\n"
            "    globs: '**/*.py'\n",
        )

        install_skill_directory(skill, CURSOR)

        frontmatter = yaml.safe_load(self._installed().split("---\n")[1])
        self.assertEqual(frontmatter["paths"], "**/*.ts")

    def test_supporting_files_ride_along(self):
        """The whole point of D8's directory install: `references/` travels with it."""
        skill = _write_skill(
            self.source,
            "fixture-skill",
            "name: fixture-skill\ndescription: A fixture.\n",
            files={"references/api.md": "# Generated\n"},
        )

        install_skill_directory(skill, CURSOR)

        self.assertEqual(
            Path(".cursor/skills/fixture-skill/references/api.md").read_text(
                encoding="utf-8"
            ),
            "# Generated\n",
        )


class TestLegacyDetectionWiredIntoInstall(unittest.TestCase):
    """§4.4: `find_legacy_installs` reaches the user's terminal through the CLI.

    Tested in isolation on the manifest; here it has to surface through the install
    itself, so the handler cannot silently grow a private "is this ours?" answer.
    """

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.source = Path(tempfile.mkdtemp())
        self.original_cwd = os.getcwd()
        os.chdir(self.test_dir)

    def tearDown(self):
        os.chdir(self.original_cwd)
        shutil.rmtree(self.test_dir)
        shutil.rmtree(self.source)

    def _fixture(self):
        return _write_skill(
            self.source,
            "fixture-skill",
            "name: fixture-skill\ndescription: A fixture.\n",
        )

    def _install_legacy_copilot_region(self):
        instructions = Path(".github/copilot-instructions.md")
        instructions.parent.mkdir(parents=True, exist_ok=True)
        instructions.write_text(
            "<!-- railtracks:fixture-skill:start -->\nold body\n"
            "<!-- railtracks:fixture-skill:end -->\n",
            encoding="utf-8",
        )

    def _install_legacy_cursor_file(self):
        rule = Path(".cursor/rules/fixture-skill.mdc")
        rule.parent.mkdir(parents=True, exist_ok=True)
        rule.write_text(
            "---\ndescription: x\nalwaysApply: false\n---\n\nold body\n",
            encoding="utf-8",
        )

    def test_a_legacy_copilot_region_is_reported_on_a_copilot_install(self):
        """The migration path: user re-runs `add copilot:x`, learns the old block is stale."""
        self._install_legacy_copilot_region()

        with patch("railtracks.cli._skillkit.install.print_warning") as mock_warning:
            install_skill_directory(self._fixture(), COPILOT, force=True)

        reported = " ".join(str(c.args[0]) for c in mock_warning.call_args_list if c.args)
        self.assertIn("copilot-instructions.md", reported)
        self.assertIn("legacy", reported)

    def test_a_legacy_cursor_mdc_is_reported_on_a_cursor_install(self):
        """The migration path: user re-runs `add cursor:x`, learns the old .mdc is stale."""
        self._install_legacy_cursor_file()

        with patch("railtracks.cli._skillkit.install.print_warning") as mock_warning:
            install_skill_directory(self._fixture(), CURSOR, force=True)

        reported = " ".join(str(c.args[0]) for c in mock_warning.call_args_list if c.args)
        self.assertIn("fixture-skill.mdc", reported)
        self.assertIn("legacy", reported)

    def test_the_legacy_install_is_reported_but_not_removed(self):
        """D12: the manifest recognises legacy installs; it never deletes them."""
        self._install_legacy_copilot_region()
        self._install_legacy_cursor_file()
        before_copilot = Path(".github/copilot-instructions.md").read_text(encoding="utf-8")
        before_cursor = Path(".cursor/rules/fixture-skill.mdc").read_text(encoding="utf-8")

        with patch("railtracks.cli._skillkit.install.print_warning"):
            install_skill_directory(self._fixture(), COPILOT, force=True)

        self.assertEqual(
            Path(".github/copilot-instructions.md").read_text(encoding="utf-8"),
            before_copilot,
        )
        self.assertEqual(
            Path(".cursor/rules/fixture-skill.mdc").read_text(encoding="utf-8"),
            before_cursor,
        )

    def test_a_clean_repo_reports_no_legacy_installs(self):
        """No legacy content on disk, no legacy warnings — the common case is silent."""
        with patch("railtracks.cli._skillkit.install.print_warning") as mock_warning:
            install_skill_directory(self._fixture(), COPILOT, force=True)

        self.assertEqual(mock_warning.call_count, 0)


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
            body=lambda s: strip_skill_arguments(s.body),
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
