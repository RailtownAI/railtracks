#!/usr/bin/env python3

"""
Basic unit tests for railtracks CLI functionality
"""

import json
import os
import shutil
import socket
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import yaml
from fastapi.testclient import TestClient
from railtracks.cli import (
    SKILLS,
    SUPPORTED_TOOLS,
    _add_claude,
    _strip_skill_arguments,
    _visual_dependencies_available,
    add_skill,
    check_for_ui_update,
    create_railtracks_dir,
    get_remote_ui_version,
    get_script_directory,
    get_stored_ui_version,
    is_port_in_use,
    list_skills,
    main,
    save_ui_version,
)
from railtracks.cli.io import (
    _print_update_available,
    print_error,
    print_status,
    print_success,
    print_warning,
)
from railtracks.cli.skill_install import CLAUDE, InstallTarget, install_skill_directory
from railtracks.cli.skill_manifest import MANIFEST_FILE, package_version, read_record
from railtracks.cli.skills_registry import load_skill
from railtracks.cli.viz_server import app


class TestUtilityFunctions(unittest.TestCase):
    """Test basic utility functions"""

    def test_get_script_directory(self):
        """Test get_script_directory returns a valid Path"""
        result = get_script_directory()
        self.assertIsInstance(result, Path)
        self.assertTrue(result.exists())
        self.assertTrue(result.is_dir())

    @patch('builtins.print')
    def test_print_functions(self, mock_print):
        """Test all print functions format messages correctly"""
        test_message = "test message"

        print_status(test_message)
        mock_print.assert_called_with("[railtracks] test message")

        print_success(test_message)
        mock_print.assert_called_with("[railtracks] test message")

        print_warning(test_message)
        mock_print.assert_called_with("[railtracks] test message")

        print_error(test_message)
        mock_print.assert_called_with("[railtracks] test message")


class TestCreateRailtracksDir(unittest.TestCase):
    """Test create_railtracks_dir function"""

    def setUp(self):
        """Set up temporary directory for testing"""
        self.test_dir = tempfile.mkdtemp()
        self.original_cwd = os.getcwd()
        self._original_railtracks_home = os.environ.pop("RAILTRACKS_HOME", None)
        os.chdir(self.test_dir)

    def tearDown(self):
        """Clean up temporary directory"""
        os.chdir(self.original_cwd)
        shutil.rmtree(self.test_dir)
        if self._original_railtracks_home is not None:
            os.environ["RAILTRACKS_HOME"] = self._original_railtracks_home

    @patch('railtracks.cli.print_status')
    @patch('railtracks.cli.print_success')
    def test_create_railtracks_dir_new(self, mock_success, mock_status):
        """Test creating .railtracks directory when it doesn't exist"""
        # Ensure .railtracks doesn't exist
        railtracks_path = Path(".railtracks")
        self.assertFalse(railtracks_path.exists())

        create_railtracks_dir()

        # Should exist now
        self.assertTrue(railtracks_path.exists())
        self.assertTrue(railtracks_path.is_dir())

        # Should have called print functions
        mock_status.assert_called()
        mock_success.assert_called()

    @patch('railtracks.cli.print_status')
    @patch('railtracks.cli.print_success')
    def test_create_railtracks_dir_existing(self, mock_success, mock_status):
        """Test when .railtracks directory already exists"""
        # Create .railtracks directory first
        railtracks_path = Path(".railtracks")
        railtracks_path.mkdir()

        create_railtracks_dir()

        # Should still exist
        self.assertTrue(railtracks_path.exists())
        self.assertTrue(railtracks_path.is_dir())

    @patch('railtracks.cli.print_status')
    @patch('railtracks.cli.print_success')
    def test_create_railtracks_dir_gitignore_new(self, mock_success, mock_status):
        """Test creating .gitignore with .railtracks entry"""
        create_railtracks_dir()

        # Should create .gitignore
        gitignore_path = Path(".gitignore")
        self.assertTrue(gitignore_path.exists())

        # Should contain .railtracks
        with open(gitignore_path) as f:
            content = f.read()
        self.assertIn(".railtracks", content)

    @patch('railtracks.cli.print_status')
    @patch('railtracks.cli.print_success')
    def test_create_railtracks_dir_gitignore_existing(self, mock_success, mock_status):
        """Test adding .railtracks to existing .gitignore"""
        # Create existing .gitignore
        gitignore_path = Path(".gitignore")
        with open(gitignore_path, "w") as f:
            f.write("*.pyc\n__pycache__/\n")

        create_railtracks_dir()

        # Should contain both old and new entries
        with open(gitignore_path) as f:
            content = f.read()
        self.assertIn("*.pyc", content)
        self.assertIn(".railtracks", content)

    @patch('railtracks.cli.print_status')
    def test_create_railtracks_dir_gitignore_already_present(self, mock_status):
        """Test when .railtracks is already in .gitignore"""
        # Create .gitignore with .railtracks already present
        gitignore_path = Path(".gitignore")
        with open(gitignore_path, "w") as f:
            f.write("*.pyc\n.railtracks\n__pycache__/\n")

        original_content = gitignore_path.read_text()

        create_railtracks_dir()

        # Content should be unchanged
        new_content = gitignore_path.read_text()
        self.assertEqual(original_content, new_content)


class TestFastAPIEndpoints(unittest.TestCase):
    """Test FastAPI endpoints"""

    def setUp(self):
        """Set up test environment"""
        self.test_dir = tempfile.mkdtemp()
        self.original_cwd = os.getcwd()
        self._original_railtracks_home = os.environ.pop("RAILTRACKS_HOME", None)
        os.chdir(self.test_dir)

        # Create .railtracks directory
        from railtracks.paths import resolve_railtracks_home
        railtracks_dir = resolve_railtracks_home()
        railtracks_dir.mkdir(parents=True, exist_ok=True)

        # Create test JSON files in root
        self.test_files = {
            "simple.json": {"test": "data"},
            "my agent session.json": {"agent": "session", "data": "test"},
            "file with spaces.json": {"spaces": "test"},
            "special-chars!@#.json": {"special": "chars"}
        }

        for filename, content in self.test_files.items():
            file_path = railtracks_dir / filename
            with open(file_path, "w") as f:
                json.dump(content, f)

        # Create test client
        self.client = TestClient(app)

    def tearDown(self):
        """Clean up test environment"""
        os.chdir(self.original_cwd)
        shutil.rmtree(self.test_dir)
        if self._original_railtracks_home is not None:
            os.environ["RAILTRACKS_HOME"] = self._original_railtracks_home

    def test_get_evaluations_empty(self):
        """Test /api/evaluations endpoint with no data directory"""
        response = self.client.get("/api/evaluations")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), [])

    def test_get_evaluations_with_data(self):
        """Test /api/evaluations endpoint with data"""
        # Create evaluations directory and files
        evaluations_dir = Path(".railtracks/data/evaluations")
        evaluations_dir.mkdir(parents=True)

        eval1 = {"id": "eval1", "score": 0.95}
        eval2 = {"id": "eval2", "score": 0.87}

        with open(evaluations_dir / "eval1.json", "w") as f:
            json.dump(eval1, f)
        with open(evaluations_dir / "eval2.json", "w") as f:
            json.dump(eval2, f)

        response = self.client.get("/api/evaluations")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data), 2)
        self.assertIn(eval1, data)
        self.assertIn(eval2, data)

    def test_get_sessions_empty(self):
        """Test /api/sessions endpoint with no data directory"""
        response = self.client.get("/api/sessions")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), [])

    def test_get_sessions_with_data(self):
        """Test /api/sessions endpoint with data"""
        # Create sessions directory and files
        sessions_dir = Path(".railtracks/data/sessions")
        sessions_dir.mkdir(parents=True)

        session1 = {"id": "session1", "status": "completed"}
        session2 = {"id": "session2", "status": "failed"}

        with open(sessions_dir / "session1.json", "w") as f:
            json.dump(session1, f)
        with open(sessions_dir / "session2.json", "w") as f:
            json.dump(session2, f)

        response = self.client.get("/api/sessions")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data), 2)
        self.assertIn(session1, data)
        self.assertIn(session2, data)

    def test_get_session_by_guid(self):
        """Test /api/sessions/{guid} endpoint with existing session"""
        # Create sessions directory and file
        sessions_dir = Path(".railtracks/data/sessions")
        sessions_dir.mkdir(parents=True)

        session_data = {"id": "test-guid-123", "status": "completed", "data": "test"}
        guid = "test-guid-123"

        with open(sessions_dir / f"{guid}.json", "w") as f:
            json.dump(session_data, f)

        response = self.client.get(f"/api/sessions/{guid}")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), session_data)

    def test_get_session_by_guid_with_flow_name_prefix(self):
        """Test /api/sessions/{guid} finds session saved as {flow_name}_{guid}.json"""
        sessions_dir = Path(".railtracks/data/sessions")
        sessions_dir.mkdir(parents=True)

        session_data = {"session_id": "abc-123-guid", "flow_name": "Stock Analysis"}
        guid = "abc-123-guid"
        with open(sessions_dir / f"Stock Analysis_{guid}.json", "w") as f:
            json.dump(session_data, f)

        response = self.client.get(f"/api/sessions/{guid}")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), session_data)

    def test_get_session_by_guid_not_found(self):
        """Test /api/sessions/{guid} endpoint with non-existent session"""
        # Create sessions directory but no file
        sessions_dir = Path(".railtracks/data/sessions")
        sessions_dir.mkdir(parents=True)

        response = self.client.get("/api/sessions/nonexistent-guid")
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json(), {"error": "Session not found"})

    def test_get_session_by_guid_invalid_json(self):
        """Test /api/sessions/{guid} endpoint with invalid JSON file"""
        # Create sessions directory and invalid JSON file
        sessions_dir = Path(".railtracks/data/sessions")
        sessions_dir.mkdir(parents=True)

        guid = "invalid-json-guid"
        invalid_file = sessions_dir / f"{guid}.json"
        with open(invalid_file, "w") as f:
            f.write("{ invalid json }")

        response = self.client.get(f"/api/sessions/{guid}")
        self.assertEqual(response.status_code, 400)
        self.assertIn("error", response.json())
        self.assertIn("Invalid JSON", response.json()["error"])


class TestSkillInstallers(unittest.TestCase):
    """Test installation of bundled AI coding assistant skills."""

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.original_cwd = os.getcwd()
        os.chdir(self.test_dir)

    def tearDown(self):
        os.chdir(self.original_cwd)
        shutil.rmtree(self.test_dir)

    def test_codex_installs_repository_skill(self):
        """Codex skills are written with valid metadata under .agents/skills."""
        add_skill("codex:agent-builder")

        target = Path(".agents/skills/agent-builder/SKILL.md")
        self.assertTrue(target.is_file())
        content = target.read_text(encoding="utf-8")
        self.assertTrue(content.startswith("---\nname: agent-builder\n"))
        self.assertIn("description:", content)
        self.assertIn("# Build a Railtracks Agent", content)

    def test_codex_does_not_use_claude_directory(self):
        """Codex installation must use its repository skill discovery path."""
        add_skill("codex:agent-builder")

        self.assertFalse(Path(".claude").exists())
        self.assertFalse(Path(".cursor").exists())

    def test_codex_resolves_argument_placeholder(self):
        """Codex documents no argument substitution, so $ARGUMENTS never survives."""
        add_skill("codex:agent-builder")

        content = Path(".agents/skills/agent-builder/SKILL.md").read_text(
            encoding="utf-8"
        )
        self.assertNotIn("$ARGUMENTS", content)

    def test_cursor_installs_rules_file(self):
        """Cursor skills are written as .mdc rules with valid metadata."""
        add_skill("cursor:agent-builder")

        target = Path(".cursor/rules/agent-builder.mdc")
        self.assertTrue(target.is_file())
        content = target.read_text(encoding="utf-8")
        self.assertTrue(content.startswith("---\ndescription: "))
        self.assertIn("alwaysApply: false", content)
        self.assertIn("# Build a Railtracks Agent", content)

    def test_cursor_does_not_use_other_tool_directories(self):
        """Cursor installation must use its own rules discovery path."""
        add_skill("cursor:agent-builder")

        self.assertFalse(Path(".claude").exists())
        self.assertFalse(Path(".agents").exists())
        self.assertFalse(Path(".github").exists())

    def test_cursor_resolves_argument_placeholder(self):
        """Cursor has no argument-hint field and no substitution, so $ARGUMENTS goes."""
        add_skill("cursor:agent-builder")

        content = Path(".cursor/rules/agent-builder.mdc").read_text(encoding="utf-8")
        self.assertNotIn("$ARGUMENTS", content)

    def test_copilot_resolves_argument_placeholder(self):
        """Copilot instructions are always-on context, so $ARGUMENTS never survives."""
        add_skill("copilot:agent-builder")

        content = Path(".github/copilot-instructions.md").read_text(encoding="utf-8")
        self.assertNotIn("$ARGUMENTS", content)
        self.assertIn("<!-- railtracks:agent-builder:start -->", content)
        self.assertIn("<!-- railtracks:agent-builder:end -->", content)

    def test_copilot_reinstall_is_idempotent(self):
        """Regenerating a skill in place must not duplicate it or add blank lines."""
        add_skill("copilot:agent-builder")
        first = Path(".github/copilot-instructions.md").read_text(encoding="utf-8")

        add_skill("copilot:agent-builder", force=True)
        second = Path(".github/copilot-instructions.md").read_text(encoding="utf-8")

        self.assertEqual(first, second)

    def test_copilot_preserves_surrounding_content(self):
        """Hand-maintained sections around the markers must survive a regeneration."""
        target = Path(".github/copilot-instructions.md")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("# Hand written preamble\n", encoding="utf-8")

        add_skill("copilot:agent-builder")
        add_skill("copilot:agent-builder", force=True)

        content = target.read_text(encoding="utf-8")
        self.assertTrue(content.startswith("# Hand written preamble\n"))
        self.assertEqual(content.count("<!-- railtracks:agent-builder:start -->"), 1)

    def test_claude_keeps_argument_placeholder(self):
        """Claude Code substitutes $ARGUMENTS at invocation, so it must be preserved."""
        add_skill("claude:agent-builder")

        content = Path(".claude/skills/agent-builder/SKILL.md").read_text(encoding="utf-8")
        self.assertIn("$ARGUMENTS", content)


def _write_skill(root, name, frontmatter, body="# Heading\n\nBody text.\n", files=None):
    """Create a synthetic skill directory and return the loaded `Skill`.

    Bundled skills deliberately ship no supporting files and no `tools:` block —
    `test_skills_registry` asserts both, as the canary for when content work starts —
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

        with patch("railtracks.cli.skill_install.print_warning") as mock_warning:
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

        with patch("railtracks.cli.skill_install.print_warning") as mock_warning:
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

        with patch("railtracks.cli.skill_install.print_status") as mock_status:
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


class TestListSkills(unittest.TestCase):
    """Test `railtracks add --list`"""

    @patch('builtins.print')
    def test_list_skills_prints_every_registered_skill(self, mock_print):
        """Every skill in the registry shows up with its description"""
        list_skills()

        output = "\n".join(str(c.args[0]) for c in mock_print.call_args_list if c.args)
        for skill_name, meta in SKILLS.items():
            self.assertIn(skill_name, output)
            self.assertIn(meta["description"], output)

    @patch('builtins.print')
    def test_list_skills_prints_supported_tools(self, mock_print):
        """The skill list is only actionable alongside the tools it installs for"""
        list_skills()

        output = "\n".join(str(c.args[0]) for c in mock_print.call_args_list if c.args)
        for tool in SUPPORTED_TOOLS:
            self.assertIn(tool, output)

    @patch('railtracks.cli.list_skills')
    def test_add_list_flag_lists_instead_of_installing(self, mock_list):
        """`add --list` short-circuits before the <tool>:<skill> requirement"""
        with patch.object(sys, 'argv', ['railtracks', 'add', '--list']):
            main()

        mock_list.assert_called_once()

    @patch('railtracks.cli.list_skills')
    def test_add_short_list_flag(self, mock_list):
        """`-l` is accepted as the short form"""
        with patch.object(sys, 'argv', ['railtracks', 'add', '-l']):
            main()

        mock_list.assert_called_once()

    @patch('railtracks.cli.print_error')
    def test_add_without_spec_still_errors(self, mock_error):
        """A bare `add`, or a lone unrelated flag, remains a usage error"""
        with patch.object(sys, 'argv', ['railtracks', 'add', '--force']):
            with self.assertRaises(SystemExit):
                main()

        mock_error.assert_called_once()


class TestPortChecking(unittest.TestCase):
    """Test port checking functionality"""

    def test_is_port_in_use_available_port(self):
        """Test is_port_in_use returns False for available port"""
        # Use a high port number that's unlikely to be in use
        test_port = 65535
        result = is_port_in_use(test_port)
        self.assertFalse(result)

    def test_is_port_in_use_occupied_port(self):
        """Test is_port_in_use returns True for occupied port"""
        # Create a socket to occupy a port
        test_port = 65534
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as test_socket:
            test_socket.bind(('localhost', test_port))
            test_socket.listen(1)

            # Now check if the port is in use
            result = is_port_in_use(test_port)
            self.assertTrue(result)

    @patch('railtracks.cli.print_error')
    @patch('railtracks.cli.is_port_in_use', return_value=True)
    @patch('railtracks.cli._visual_dependencies_available', return_value=True)
    @patch('railtracks.cli.sys.argv', ['railtracks', 'viz'])
    def test_viz_command_port_in_use(self, _mock_deps, _mock_port, mock_print_error):
        """Test viz command exits with error when port is in use"""
        with self.assertRaises(SystemExit) as ctx:
            main()

        self.assertEqual(ctx.exception.code, 1)
        mock_print_error.assert_any_call("Port 3030 is already in use!")

    def test_viz_command_port_available(self):
        """Test viz command behavior when port is available"""
        # Test that the port checking function works correctly
        # This is more of an integration test of the port checking logic

        # Test with a port that should be available
        test_port = 65533
        result = is_port_in_use(test_port)

        # The result should be a boolean
        self.assertIsInstance(result, bool)

        # If the port is available, we should be able to bind to it
        if not result:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as test_socket:
                try:
                    test_socket.bind(('localhost', test_port))
                    # If we get here, the port was indeed available
                    self.assertFalse(result)
                except OSError:
                    # Port became unavailable between checks
                    pass

    def test_port_checking_with_different_ports(self):
        """Test port checking with various port numbers"""
        # Test with a range of ports
        test_ports = [8080, 3000, 5000, 9000]

        for port in test_ports:
            result = is_port_in_use(port)
            # Result should be boolean
            self.assertIsInstance(result, bool)

            # If port is available, we should be able to bind to it
            if not result:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as test_socket:
                    try:
                        test_socket.bind(('localhost', port))
                        # If we get here, the port was indeed available
                        self.assertFalse(result)
                    except OSError:
                        # Port became unavailable between checks
                        pass

    def test_port_checking_edge_cases(self):
        """Test port checking with edge cases"""
        # Test with invalid port numbers
        with self.assertRaises(OverflowError):
            is_port_in_use(-1)

        # Port 0 is actually valid (lets OS assign port)
        result = is_port_in_use(0)
        self.assertIsInstance(result, bool)

        with self.assertRaises(OverflowError):
            is_port_in_use(65536)  # Port number too high

    @patch('railtracks.cli.socket.socket')
    def test_port_checking_socket_error(self, mock_socket_class):
        """Test port checking when socket operations fail"""
        # Mock socket to raise OSError
        mock_socket = MagicMock()
        mock_socket.bind.side_effect = OSError("Socket error")
        mock_socket_class.return_value.__enter__.return_value = mock_socket

        result = is_port_in_use(3030)
        self.assertTrue(result)  # Should return True when socket fails to bind

class TestUIVersionTracking(unittest.TestCase):
    """Test UI version persistence and update-check logic"""

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.original_cwd = os.getcwd()
        self._original_railtracks_home = os.environ.pop("RAILTRACKS_HOME", None)
        os.chdir(self.test_dir)
        # Create .railtracks dir so the version file path is valid
        Path(".railtracks").mkdir()

    def tearDown(self):
        os.chdir(self.original_cwd)
        shutil.rmtree(self.test_dir)
        if self._original_railtracks_home is not None:
            os.environ["RAILTRACKS_HOME"] = self._original_railtracks_home

    # --- get_stored_ui_version ---

    def test_get_stored_ui_version_no_file(self):
        """Returns None when the version file does not exist"""
        result = get_stored_ui_version()
        self.assertIsNone(result)

    def test_get_stored_ui_version_with_file(self):
        """Returns the stored version string when the file exists"""
        Path(".railtracks/.ui_version").write_text('"abc-etag-123"')
        result = get_stored_ui_version()
        self.assertEqual(result, '"abc-etag-123"')

    def test_get_stored_ui_version_strips_whitespace(self):
        """Strips leading/trailing whitespace from the stored value"""
        Path(".railtracks/.ui_version").write_text('  etag-value  \n')
        result = get_stored_ui_version()
        self.assertEqual(result, 'etag-value')

    # --- save_ui_version ---

    def test_save_ui_version_writes_file(self):
        """Writes the version string to the version file"""
        save_ui_version('"new-etag"')
        content = Path(".railtracks/.ui_version").read_text()
        self.assertEqual(content, '"new-etag"')

    def test_save_ui_version_overwrites_existing(self):
        """Overwrites an existing version file"""
        Path(".railtracks/.ui_version").write_text('old-etag')
        save_ui_version('new-etag')
        self.assertEqual(Path(".railtracks/.ui_version").read_text(), 'new-etag')

    # --- get_remote_ui_version ---

    @patch('railtracks.cli.urllib.request.urlopen')
    def test_get_remote_ui_version_returns_etag(self, mock_urlopen):
        """Returns the ETag header from the remote HEAD response"""
        mock_response = MagicMock()
        mock_response.headers.get.side_effect = lambda k: '"remote-etag"' if k == 'ETag' else None
        mock_urlopen.return_value.__enter__.return_value = mock_response

        result = get_remote_ui_version()
        self.assertEqual(result, '"remote-etag"')

    @patch('railtracks.cli.urllib.request.urlopen')
    def test_get_remote_ui_version_falls_back_to_last_modified(self, mock_urlopen):
        """Falls back to Last-Modified when ETag is absent"""
        mock_response = MagicMock()
        mock_response.headers.get.side_effect = lambda k: 'Mon, 16 Mar 2026 00:00:00 GMT' if k == 'Last-Modified' else None
        mock_urlopen.return_value.__enter__.return_value = mock_response

        result = get_remote_ui_version()
        self.assertEqual(result, 'Mon, 16 Mar 2026 00:00:00 GMT')

    @patch('railtracks.cli.urllib.request.urlopen', side_effect=Exception('network error'))
    def test_get_remote_ui_version_returns_none_on_error(self, _mock_urlopen):
        """Returns None when the network request fails"""
        result = get_remote_ui_version()
        self.assertIsNone(result)

    # --- check_for_ui_update ---

    @patch('railtracks.cli._print_update_available')
    def test_check_no_stored_version_skips_check(self, mock_print):
        """Does nothing when no version is stored (first-time install)"""
        check_for_ui_update()
        mock_print.assert_not_called()

    @patch('railtracks.cli.get_remote_ui_version', return_value=None)
    @patch('railtracks.cli._print_update_available')
    def test_check_remote_unavailable_skips_warning(self, mock_print, _mock_remote):
        """Does not warn when the remote version cannot be fetched"""
        Path(".railtracks/.ui_version").write_text('stored-etag')
        check_for_ui_update()
        mock_print.assert_not_called()

    @patch('railtracks.cli.get_remote_ui_version', return_value='stored-etag')
    @patch('railtracks.cli._print_update_available')
    def test_check_versions_match_no_warning(self, mock_print, _mock_remote):
        """Does not warn when stored and remote versions are the same"""
        Path(".railtracks/.ui_version").write_text('stored-etag')
        check_for_ui_update()
        mock_print.assert_not_called()

    @patch('railtracks.cli.get_remote_ui_version', return_value='new-etag')
    @patch('railtracks.cli._print_update_available')
    def test_check_versions_differ_shows_warning(self, mock_print, _mock_remote):
        """Calls _print_update_available when remote version differs from stored"""
        Path(".railtracks/.ui_version").write_text('old-etag')
        check_for_ui_update()
        mock_print.assert_called_once()

    # --- _print_update_available ---

    @patch('builtins.print')
    def test_print_update_available_contains_update_command(self, mock_print):
        """Printed message includes the 'railtracks update' command"""
        _print_update_available()
        mock_print.assert_called_once()
        printed_text = mock_print.call_args[0][0]
        self.assertIn('railtracks update', printed_text)

    # --- version file location ---

    def test_ui_version_file_inside_railtracks_home(self):
        """Version file is stored inside the resolved railtracks home directory"""
        from railtracks.paths import resolve_railtracks_home
        version_file = resolve_railtracks_home() / ".ui_version"
        save_ui_version("test-etag")
        self.assertTrue(
            version_file.exists(),
            f"Version file not found at expected location: {version_file}",
        )

    # --- temp file cleanup on failure ---

    @patch('railtracks.cli.sys.exit')
    @patch('railtracks.cli.urllib.request.urlopen')
    def test_temp_file_deleted_on_extraction_failure(self, mock_urlopen, mock_exit):
        """Temp zip file is cleaned up even when zip extraction fails"""
        # Provide a response that returns invalid zip bytes
        mock_response = MagicMock()
        mock_response.__enter__ = lambda s: s
        mock_response.__exit__ = MagicMock(return_value=False)
        mock_response.headers.get.return_value = None
        mock_response.read.return_value = b"not a zip file"
        mock_urlopen.return_value = mock_response

        captured_paths = []
        real_named_temporary_file = tempfile.NamedTemporaryFile

        def capturing_ntf(**kwargs):
            f = real_named_temporary_file(**kwargs)
            captured_paths.append(f.name)
            return f

        with patch('railtracks.cli.tempfile.NamedTemporaryFile', side_effect=capturing_ntf):
            import railtracks.cli as cli_module
            cli_module.download_and_extract_ui()

        # sys.exit should have been called due to BadZipFile
        mock_exit.assert_called()
        # The temp file should have been deleted by the finally block
        for path in captured_paths:
            self.assertFalse(os.path.exists(path), f"Temp file {path} was not cleaned up")

    # --- background thread for update check ---

    @patch('railtracks.cli.download_and_extract_ui')
    @patch('railtracks.cli.check_for_ui_update')
    @patch('railtracks.cli.viz_server.RailtracksServer')
    @patch('railtracks.cli.create_railtracks_dir')
    @patch('railtracks.cli.is_port_in_use', return_value=False)
    @patch('railtracks.cli._visual_dependencies_available', return_value=True)
    @patch('railtracks.cli.sys.argv', ['railtracks', 'viz'])
    def test_viz_runs_update_check_in_background_thread(self, _mock_deps, _mock_port,
                                                         _mock_dir, mock_server,
                                                         mock_check, mock_download):
        """viz command runs check_for_ui_update in a daemon thread, not blocking main"""
        Path(".railtracks/ui").mkdir(parents=True, exist_ok=True)
        Path(".railtracks/ui/index.html").write_text("ok")
        thread_kwargs = {}

        real_thread = threading.Thread

        def capturing_thread(**kwargs):
            if kwargs.get('target') is mock_check:
                thread_kwargs.update(kwargs)
            return real_thread(**kwargs)

        mock_server_instance = MagicMock()
        mock_server.return_value = mock_server_instance

        import railtracks.cli as cli_module
        with patch('railtracks.cli.threading.Thread', side_effect=capturing_thread):
            cli_module.main()

        self.assertIs(thread_kwargs.get('target'), mock_check,
                      "check_for_ui_update should be the thread target")
        self.assertTrue(thread_kwargs.get('daemon'),
                        "Update-check thread should be a daemon thread")
        mock_download.assert_not_called()

    @patch('railtracks.cli.download_and_extract_ui')
    @patch('railtracks.cli.viz_server.RailtracksServer')
    @patch('railtracks.cli.create_railtracks_dir')
    @patch('railtracks.cli.is_port_in_use', return_value=False)
    @patch('railtracks.cli._visual_dependencies_available', return_value=True)
    @patch('railtracks.cli.sys.argv', ['railtracks', 'viz'])
    def test_viz_downloads_ui_when_bundle_missing(self, _mock_deps, _mock_port,
                                                  _mock_dir, mock_server,
                                                  mock_download):
        """viz command downloads UI bundle when local index.html is missing"""
        mock_server_instance = MagicMock()
        mock_server.return_value = mock_server_instance

        import railtracks.cli as cli_module
        cli_module.main()

        mock_download.assert_called_once()


class TestMainDispatch(unittest.TestCase):
    """Test the main() CLI entrypoint dispatching"""

    @patch('railtracks.cli._print_help')
    @patch('railtracks.cli.sys.argv', ['railtracks'])
    def test_no_args_shows_help_and_exits(self, mock_help):
        """main() with no command shows help and exits"""
        with self.assertRaises(SystemExit) as ctx:
            main()
        self.assertEqual(ctx.exception.code, 1)
        mock_help.assert_called_once()

    @patch('builtins.print')
    @patch('railtracks.cli.sys.argv', ['railtracks', 'bogus'])
    def test_unknown_command_exits(self, mock_print):
        """main() with an unknown command prints error and exits"""
        with self.assertRaises(SystemExit) as ctx:
            main()
        self.assertEqual(ctx.exception.code, 1)
        printed = [call[0][0] for call in mock_print.call_args_list]
        self.assertTrue(any('bogus' in s for s in printed))

    @patch('railtracks.cli.print_error')
    @patch('railtracks.cli.print_status')
    @patch('railtracks.cli._visual_dependencies_available', return_value=False)
    @patch('railtracks.cli.sys.argv', ['railtracks', 'viz'])
    def test_viz_exits_when_visual_deps_missing(self, _mock_deps,
                                                mock_status, mock_error):
        """main() viz exits gracefully when visual extras are not installed"""
        with self.assertRaises(SystemExit) as ctx:
            main()
        self.assertEqual(ctx.exception.code, 1)
        error_messages = ' '.join(c[0][0] for c in mock_error.call_args_list)
        self.assertIn('optional dependencies', error_messages)

    @patch('railtracks.cli.init_railtracks')
    @patch('railtracks.cli.sys.argv', ['railtracks', 'init'])
    def test_init_command(self, mock_init):
        """main() dispatches 'init' to init_railtracks()"""
        main()
        mock_init.assert_called_once()

    @patch('railtracks.cli.update_railtracks')
    @patch('railtracks.cli.sys.argv', ['railtracks', 'update'])
    def test_update_command(self, mock_update):
        """main() dispatches 'update' to update_railtracks()"""
        main()
        mock_update.assert_called_once()

    @patch('railtracks.cli.print_error')
    @patch('railtracks.cli.sys.argv', ['railtracks', 'add'])
    def test_add_no_spec_exits(self, mock_error):
        """main() add with no spec shows usage and exits"""
        with self.assertRaises(SystemExit) as ctx:
            main()
        self.assertEqual(ctx.exception.code, 1)


class TestVisualDepsCheck(unittest.TestCase):
    """Test _visual_dependencies_available()"""

    @patch('railtracks.cli.importlib.util.find_spec')
    def test_returns_true_when_both_present(self, mock_find_spec):
        mock_find_spec.return_value = MagicMock()
        self.assertTrue(_visual_dependencies_available())

    @patch('railtracks.cli.importlib.util.find_spec')
    def test_returns_false_when_fastapi_missing(self, mock_find_spec):
        mock_find_spec.side_effect = lambda name: None if name == 'fastapi' else MagicMock()
        self.assertFalse(_visual_dependencies_available())

    @patch('railtracks.cli.importlib.util.find_spec')
    def test_returns_false_when_uvicorn_missing(self, mock_find_spec):
        mock_find_spec.side_effect = lambda name: None if name == 'uvicorn' else MagicMock()
        self.assertFalse(_visual_dependencies_available())


class TestLazyGetattr(unittest.TestCase):
    """Test __getattr__ lazy exports on railtracks.cli"""

    def test_app_resolves(self):
        """railtracks.cli.app lazily loads the FastAPI app from viz_server"""
        import railtracks.cli as cli_module
        self.assertIsNotNone(cli_module.app)
        from railtracks.cli.viz_server import app as direct_app
        self.assertIs(cli_module.app, direct_app)

    def test_railtracks_server_resolves(self):
        """railtracks.cli.RailtracksServer lazily loads the class from viz_server"""
        import railtracks.cli as cli_module
        from railtracks.cli.viz_server import RailtracksServer
        self.assertIs(cli_module.RailtracksServer, RailtracksServer)

    def test_unknown_attr_raises(self):
        """Accessing an undefined name raises AttributeError"""
        import railtracks.cli as cli_module
        with self.assertRaises(AttributeError):
            _ = cli_module.nonexistent_thing


if __name__ == "__main__":
    unittest.main()
