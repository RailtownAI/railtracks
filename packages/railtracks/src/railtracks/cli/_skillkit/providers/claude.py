"""The Claude Code install target.

Native path: `.claude/skills/<name>/`. Consumes `name`, `description`,
`argument-hint`, plus whatever the skill puts under `tools.claude`:
`allowed-tools`, `disallowed-tools`, `paths`, `disable-model-invocation`.
"""

from __future__ import annotations

from pathlib import Path

from ..install import InstallTarget, render_frontmatter
from ..registry import Skill


def _frontmatter(skill: Skill) -> str:
    """Project a skill into the frontmatter Claude Code consumes.

    `name` and `description` map across directly; `argument-hint` is emitted when
    the skill has one; `tools.claude` supplies everything else. Every value is
    escaped by `render_frontmatter`, so brackets and colons survive a round-trip.
    """
    return render_frontmatter(
        (
            ("name", skill.name),
            ("description", skill.description),
            ("argument-hint", skill.argument_hint),
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
