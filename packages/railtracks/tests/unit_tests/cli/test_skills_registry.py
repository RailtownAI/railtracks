"""Tests for the on-disk skill format and the discovery layer that reads it."""

import pytest
from railtracks.cli import SKILLS
from railtracks.cli.skills_registry import (
    SkillFormatError,
    default_skills_directory,
    discover_skills,
    load_skill,
)

BUNDLED_SKILLS = ("agent-builder", "middleware", "rag-pipeline")


def write_skill(
    root,
    name,
    frontmatter="name: {name}\ndescription: A test skill.\n",
    body="# Heading\n\nBody text.\n",
    dirname=None,
):
    """Create a skill directory under `root` and return its path."""
    directory = root / (dirname or name)
    directory.mkdir(parents=True, exist_ok=True)
    front = frontmatter.format(name=name)
    (directory / "SKILL.md").write_text(f"---\n{front}---\n\n{body}", encoding="utf-8")
    return directory


# --- discovery of the bundled skills ---------------------------------------


class TestBundledSkills:
    def test_discovers_every_bundled_skill(self):
        """All three shipped skills are found, keyed and ordered by name."""
        skills = discover_skills()

        assert tuple(skills) == BUNDLED_SKILLS

    @pytest.mark.parametrize("name", BUNDLED_SKILLS)
    def test_metadata_comes_from_frontmatter(self, name):
        """Each skill's name matches its directory and carries usable metadata."""
        skill = discover_skills()[name]

        assert skill.name == name
        assert skill.directory == default_skills_directory() / name
        assert skill.description.strip()
        assert skill.argument_hint is not None and skill.argument_hint.strip()

    @pytest.mark.parametrize("name", BUNDLED_SKILLS)
    def test_body_excludes_frontmatter(self, name):
        """The body handlers install must not carry the source frontmatter."""
        skill = discover_skills()[name]

        assert not skill.body.startswith("---")
        assert skill.body.startswith("# ")

    @pytest.mark.parametrize("name", BUNDLED_SKILLS)
    def test_bundled_skills_have_no_supporting_files(self, name):
        """Nothing bundled ships extras yet; a regression here is worth seeing."""
        assert discover_skills()[name].supporting_files == ()

    @pytest.mark.parametrize("name", BUNDLED_SKILLS)
    def test_bundled_skills_declare_no_tool_overrides(self, name):
        """No handler reads `tools:` yet, so nothing bundled should author it."""
        assert discover_skills()[name].tools == {}


class TestLegacySkillsMapping:
    """`SKILLS` must expose the same keys and values the hardcoded dict did."""

    def test_keys_match_the_old_hardcoded_dict(self):
        assert set(SKILLS) == set(BUNDLED_SKILLS)

    def test_agent_builder_values_match(self):
        assert SKILLS["agent-builder"] == {
            "name": "agent-builder",
            "description": (
                "Build an agent using the railtracks Python framework. "
                "Use when the user wants to create an AI agent, tool-calling workflow, "
                "or multi-agent system with railtracks."
            ),
            "argument_hint": "[describe what the agent should do]",
        }

    def test_rag_pipeline_values_match(self):
        assert SKILLS["rag-pipeline"] == {
            "name": "rag-pipeline",
            "description": (
                "Build a RAG (retrieval-augmented generation) pipeline using railtracks. "
                "Use when the user wants to ingest documents into a vector store and retrieve "
                "relevant passages to answer questions."
            ),
            "argument_hint": "[describe the data source and what you want to retrieve]",
        }

    def test_middleware_values_match(self):
        assert SKILLS["middleware"] == {
            "name": "middleware",
            "description": (
                "Use middleware as part of your railtracks agent. Use when you want build resilient and effective agents"
            ),
            "argument_hint": "[describe the middleware to implement]",
        }


# --- schema ----------------------------------------------------------------


class TestSchema:
    def test_argument_hint_is_optional(self, tmp_path):
        directory = write_skill(
            tmp_path, "hintless", frontmatter="name: hintless\ndescription: No hint.\n"
        )

        assert load_skill(directory).argument_hint is None

    def test_supporting_files_are_listed_relative_and_sorted(self, tmp_path):
        directory = write_skill(tmp_path, "with-extras")
        (directory / "references").mkdir()
        (directory / "references" / "api.md").write_text("x", encoding="utf-8")
        (directory / "helper.py").write_text("x", encoding="utf-8")

        supporting = load_skill(directory).supporting_files

        assert [str(p) for p in supporting] == ["helper.py", "references/api.md"]

    def test_bytecode_cache_is_not_a_supporting_file(self, tmp_path):
        """A skill that ships Python helpers must not list its own __pycache__."""
        directory = write_skill(tmp_path, "with-cache")
        (directory / "__pycache__").mkdir()
        (directory / "__pycache__" / "helper.cpython-312.pyc").write_text("x")

        assert load_skill(directory).supporting_files == ()

    def test_unknown_key_inside_tools_block_is_preserved(self, tmp_path):
        """Lax inside `tools:` — an unknown assistant is one we don't ship support for."""
        directory = write_skill(
            tmp_path,
            "laxity",
            frontmatter=(
                "name: laxity\n"
                "description: Lax inside tools.\n"
                "tools:\n"
                "  windsurf:\n"
                "    someFutureKey: yes-please\n"
                "  cursor:\n"
                "    globs: '**/*.py'\n"
            ),
        )

        tools = load_skill(directory).tools

        assert tools["windsurf"]["someFutureKey"] == "yes-please"
        assert tools["cursor"]["globs"] == "**/*.py"


# --- validation ------------------------------------------------------------


class TestValidation:
    """Every failure must name the offending directory."""

    def test_missing_skill_file(self, tmp_path):
        (tmp_path / "empty-skill").mkdir()

        with pytest.raises(SkillFormatError, match="empty-skill"):
            load_skill(tmp_path / "empty-skill")

    def test_missing_frontmatter(self, tmp_path):
        directory = tmp_path / "bare"
        directory.mkdir()
        (directory / "SKILL.md").write_text("# Just a heading\n", encoding="utf-8")

        with pytest.raises(SkillFormatError, match="bare"):
            load_skill(directory)

    def test_unterminated_frontmatter(self, tmp_path):
        directory = tmp_path / "unterminated"
        directory.mkdir()
        (directory / "SKILL.md").write_text(
            "---\nname: unterminated\ndescription: x\n", encoding="utf-8"
        )

        with pytest.raises(SkillFormatError, match="unterminated"):
            load_skill(directory)

    def test_unparseable_frontmatter(self, tmp_path):
        directory = tmp_path / "broken-yaml"
        directory.mkdir()
        (directory / "SKILL.md").write_text(
            "---\nname: [unclosed\n---\n\nbody\n", encoding="utf-8"
        )

        with pytest.raises(SkillFormatError, match="broken-yaml"):
            load_skill(directory)

    def test_unknown_top_level_key_is_rejected(self, tmp_path):
        """Strict at the top level — a typo silently loses metadata for every tool."""
        directory = write_skill(
            tmp_path,
            "typo",
            frontmatter=(
                'name: typo\ndescription: Typo\'d hint key.\narguments-hint: "[oops]"\n'
            ),
        )

        with pytest.raises(SkillFormatError, match="typo") as excinfo:
            load_skill(directory)
        assert "arguments-hint" in str(excinfo.value)

    def test_missing_description(self, tmp_path):
        directory = write_skill(tmp_path, "no-desc", frontmatter="name: no-desc\n")

        with pytest.raises(SkillFormatError, match="no-desc"):
            load_skill(directory)

    def test_empty_description(self, tmp_path):
        directory = write_skill(
            tmp_path, "blank-desc", frontmatter="name: blank-desc\ndescription: '  '\n"
        )

        with pytest.raises(SkillFormatError, match="blank-desc"):
            load_skill(directory)

    def test_missing_name(self, tmp_path):
        directory = write_skill(tmp_path, "no-name", frontmatter="description: x\n")

        with pytest.raises(SkillFormatError, match="no-name"):
            load_skill(directory)

    def test_name_must_match_directory(self, tmp_path):
        directory = write_skill(
            tmp_path,
            "declared-name",
            frontmatter="name: declared-name\ndescription: Mismatched.\n",
            dirname="actual-dir",
        )

        with pytest.raises(SkillFormatError, match="actual-dir"):
            load_skill(directory)

    def test_tools_must_be_a_mapping(self, tmp_path):
        directory = write_skill(
            tmp_path,
            "bad-tools",
            frontmatter="name: bad-tools\ndescription: x\ntools:\n  - cursor\n",
        )

        with pytest.raises(SkillFormatError, match="bad-tools"):
            load_skill(directory)

    def test_discovery_surfaces_a_broken_skill(self, tmp_path):
        """One malformed directory fails the whole scan rather than being skipped."""
        write_skill(tmp_path, "fine")
        (tmp_path / "not-a-skill").mkdir()

        with pytest.raises(SkillFormatError, match="not-a-skill"):
            discover_skills(tmp_path)
