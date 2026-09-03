"""The Claude Code install target.

Native path: `.claude/skills/<name>/`. Consumes `name`, `description`,
`argument-hint`, plus whatever the skill puts under `tools.claude`:
`allowed-tools`, `disallowed-tools`, `paths`, `disable-model-invocation`.
"""

from __future__ import annotations

from pathlib import Path

from ..install import InstallTarget, render_frontmatter
from ..registry import Skill


def _quote(value: str) -> str:
    """Emit a string as a double-quoted YAML scalar.

    `argument-hint` is the only field that reaches SKILL.md pre-quoted — its value
    can contain brackets and colons and we want it to survive a round-trip through
    the reader unchanged. Every other field is either a bare identifier or a nested
    structure `yaml.safe_dump` renders correctly on its own.
    """
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def _frontmatter(skill: Skill) -> str:
    """Project a skill into the frontmatter Claude Code consumes.

    `name` and `description` map across directly; `argument-hint` is emitted when
    the skill has one; `tools.claude` supplies everything else.
    """
    return render_frontmatter(
        (
            ("name", skill.name),
            ("description", skill.description),
            (
                "argument-hint",
                _quote(skill.argument_hint)
                if skill.argument_hint is not None
                else None,
            ),
        ),
        skill.tools.get("claude"),
        skill_name=skill.name,
    )


CLAUDE = InstallTarget(
    key="claude",
    label="Claude Code",
    root=Path(".claude") / "skills",
    # Claude Code substitutes $ARGUMENTS itself, so its body ships as authored.
    body=lambda skill: skill.body,
    frontmatter=_frontmatter,
)
