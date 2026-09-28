"""The Codex install target.

Native path: `.agents/skills/<name>/`. Codex reads only `name` and `description`
from `SKILL.md`. An `agents/openai.yaml` sidecar would carry invocation policy
and MCP dependencies, but nothing about it belongs in the frontmatter.
"""

from __future__ import annotations

from pathlib import Path

from ..install import InstallTarget, render_frontmatter, strip_skill_arguments
from ..registry import Skill


def _frontmatter(skill: Skill) -> str:
    """Project a skill into the frontmatter Codex consumes.

    `tools.codex` is passed through so a forward-added key survives, though no
    key is defined for it today.
    """
    return render_frontmatter(
        (
            ("name", skill.name),
            ("description", skill.description),
        ),
        skill.tools.get("codex"),
        skill_name=skill.name,
    )


CODEX = InstallTarget(
    key="codex",
    label="Codex",
    root=Path(".agents") / "skills",
    body=lambda skill: strip_skill_arguments(skill.body),
    frontmatter=_frontmatter,
)
