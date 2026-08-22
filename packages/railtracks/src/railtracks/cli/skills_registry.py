"""Discovery and validation of the bundled skill directories.

A skill is a directory under ``cli/skills/`` containing a ``SKILL.md`` whose YAML
frontmatter carries the metadata the CLI used to hardcode:

---
name: agent-builder            # required, must equal the directory name
description: ...               # required, non-empty
argument-hint: "[...]"         # optional
tools:                         # optional, per-assistant overrides
    cursor:
    globs: "**/*.py"
    alwaysApply: false
    claude:
    allowed-tools: [Read, Edit, Bash]
---
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Any, Mapping

import yaml

SKILL_FILE = "SKILL.md"

_REQUIRED_KEYS = ("name", "description")
_OPTIONAL_KEYS = ("argument-hint", "tools")
_ALLOWED_KEYS = frozenset(_REQUIRED_KEYS + _OPTIONAL_KEYS)

_IGNORED_DIR_NAMES = frozenset({"__pycache__"})


class SkillFormatError(Exception):
    """A bundled skill directory does not satisfy the on-disk skill format.

    Deliberately its own type rather than ``ValueError``: callers need to tell a
    malformed skill apart from any other bad value, and the CLI is the only thing
    that should be reporting it.
    """


@dataclass(frozen=True)
class Skill:
    """One discovered skill directory.

    Attributes:
        name: The skill's identifier; always equal to the directory name.
        description: One-line summary, used to decide when the skill applies.
        argument_hint: Placeholder text for the skill's argument, if it takes one.
        body: The Markdown body with the frontmatter block stripped.
        directory: Path to the skill directory itself.
        supporting_files: Every other file in the directory, relative to it, sorted.
        tools: Per-assistant overrides, keyed by assistant name. Read-only.
    """

    name: str
    description: str
    argument_hint: str | None
    body: str
    directory: Path
    supporting_files: tuple[Path, ...]
    tools: Mapping[str, Mapping[str, Any]]

    def as_meta(self) -> dict[str, Any]:
        """The legacy ``SKILLS[...]`` mapping shape, for callers that predate `Skill`."""
        return {
            "name": self.name,
            "description": self.description,
            "argument_hint": self.argument_hint,
        }


def _split_frontmatter(text: str) -> tuple[str, str] | None:
    """Split `text` into (raw YAML, body), or None if it opens with no frontmatter."""
    lines = text.splitlines(keepends=True)
    if not lines or lines[0].strip() != "---":
        return None
    for idx in range(1, len(lines)):
        # Leave the blank line before the first heading with frontmatter so handlers can re-emit it correctly.
        if lines[idx].strip() == "---":
            return "".join(lines[1:idx]), "".join(lines[idx + 1 :]).lstrip("\n")
    return None


def _parse_tools(raw: Any, directory: Path) -> Mapping[str, Mapping[str, Any]]:
    """Validate the outer shape of a `tools:` block, leaving its contents alone.

    Unknown assistant names and unknown keys within them are preserved verbatim: an
    unrecognised `tools.windsurf` is an assistant this version does not support yet,
    and rejecting it would make the schema a blocker for adding assistants later.
    """
    if raw is None:
        return MappingProxyType({})
    if not isinstance(raw, dict):
        raise SkillFormatError(
            f"skill '{directory.name}': 'tools' must be a mapping of assistant name "
            f"to its settings, got {type(raw).__name__}."
        )
    parsed: dict[str, Mapping[str, Any]] = {}
    for assistant, settings in raw.items():
        if not isinstance(settings, dict):
            raise SkillFormatError(
                f"skill '{directory.name}': 'tools.{assistant}' must be a mapping, "
                f"got {type(settings).__name__}."
            )
        parsed[str(assistant)] = MappingProxyType(dict(settings))
    return MappingProxyType(parsed)


def _supporting_files(directory: Path) -> tuple[Path, ...]:
    """Every file in `directory` other than SKILL.md, relative to it and sorted."""
    found = []
    for path in directory.rglob("*"):
        if not path.is_file():
            continue
        relative = path.relative_to(directory)
        if relative == Path(SKILL_FILE):
            continue
        if any(
            part in _IGNORED_DIR_NAMES or part.startswith(".")
            for part in relative.parts
        ):
            continue
        found.append(relative)
    return tuple(sorted(found))


def _read_skill_file(directory: Path) -> tuple[dict[str, Any], str]:
    """Read `directory/SKILL.md` and return its parsed frontmatter and body."""
    skill_file = directory / SKILL_FILE
    if not skill_file.is_file():
        raise SkillFormatError(
            f"skill '{directory.name}': no {SKILL_FILE} found in {directory}."
        )

    split = _split_frontmatter(skill_file.read_text(encoding="utf-8"))
    if split is None:
        raise SkillFormatError(
            f"skill '{directory.name}': {SKILL_FILE} must begin with a YAML "
            f"frontmatter block delimited by '---' lines."
        )
    raw_frontmatter, body = split

    try:
        frontmatter = yaml.safe_load(raw_frontmatter)
    except yaml.YAMLError as e:
        raise SkillFormatError(
            f"skill '{directory.name}': frontmatter is not valid YAML: {e}"
        ) from e

    if frontmatter is None:
        frontmatter = {}
    if not isinstance(frontmatter, dict):
        raise SkillFormatError(
            f"skill '{directory.name}': frontmatter must be a mapping, "
            f"got {type(frontmatter).__name__}."
        )
    return frontmatter, body


def load_skill(directory: Path) -> Skill:
    """Read and validate one skill directory. Raises `SkillFormatError` if invalid."""
    frontmatter, body = _read_skill_file(directory)

    # raise error on unknown keys
    unknown = sorted(set(frontmatter) - _ALLOWED_KEYS)
    if unknown:
        raise SkillFormatError(
            f"skill '{directory.name}': unknown frontmatter key(s) "
            f"{', '.join(repr(k) for k in unknown)}. "
            f"Allowed: {', '.join(sorted(_ALLOWED_KEYS))}."
        )

    name = frontmatter.get("name")
    if not isinstance(name, str) or not name.strip():
        raise SkillFormatError(
            f"skill '{directory.name}': frontmatter is missing a non-empty 'name'."
        )
    if name != directory.name:
        raise SkillFormatError(
            f"skill '{directory.name}': frontmatter 'name' is {name!r}, which does "
            f"not match the directory name {directory.name!r}."
        )

    description = frontmatter.get("description")
    if not isinstance(description, str) or not description.strip():
        raise SkillFormatError(
            f"skill '{directory.name}': frontmatter is missing a non-empty "
            f"'description'."
        )

    argument_hint = frontmatter.get("argument-hint")
    if argument_hint is not None and not isinstance(argument_hint, str):
        raise SkillFormatError(
            f"skill '{directory.name}': 'argument-hint' must be a string, "
            f"got {type(argument_hint).__name__}."
        )

    return Skill(
        name=name,
        description=description,
        argument_hint=argument_hint,
        body=body,
        directory=directory,
        supporting_files=_supporting_files(directory),
        tools=_parse_tools(frontmatter.get("tools"), directory),
    )


def default_skills_directory() -> Path:
    """The directory the bundled skills are shipped in."""
    return Path(__file__).parent / "skills"


def discover_skills(skills_dir: Path | None = None) -> dict[str, Skill]:
    """Load every skill directory under `skills_dir`, keyed by name, sorted by name.

    Args:
        skills_dir: Directory to scan. Defaults to the bundled `cli/skills/`.

    Raises:
        SkillFormatError: If any directory in the scan is not a valid skill.
    """
    root = default_skills_directory() if skills_dir is None else skills_dir
    if not root.is_dir():
        return {}

    candidates = [
        entry
        for entry in root.iterdir()
        if entry.is_dir()
        and entry.name not in _IGNORED_DIR_NAMES
        and not entry.name.startswith(".")
    ]
    return {
        skill.name: skill
        for skill in sorted(map(load_skill, candidates), key=lambda s: s.name)
    }
