"""The GitHub Copilot install target.

Native path: `.github/skills/<name>/`. Copilot reads `name` and `description`,
and consumes `allowed-tools` and `license` from `tools.copilot`. The old
marker-block in `.github/copilot-instructions.md` is not written any more;
`find_legacy_installs` reports it if it is still on disk.
"""

from __future__ import annotations

from pathlib import Path

from ..install import InstallTarget, render_frontmatter, strip_skill_arguments
from ..registry import Skill


def _frontmatter(skill: Skill) -> str:
    """Project a skill into the frontmatter Copilot consumes.

    `argument-hint` is Claude-only and stays a top-level key on the source; it
    never reaches this projection.
    """
    return render_frontmatter(
        (
            ("name", skill.name),
            ("description", skill.description),
        ),
        skill.tools.get("copilot"),
        skill_name=skill.name,
    )


COPILOT = InstallTarget(
    key="copilot",
    label="GitHub Copilot",
    root=Path(".github") / "skills",
    body=lambda skill: strip_skill_arguments(skill.body),
    frontmatter=_frontmatter,
)
