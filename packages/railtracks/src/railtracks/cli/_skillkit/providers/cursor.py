"""The Cursor install target.

Native path: `.cursor/skills/<name>/`. Cursor reads `name` (which must equal the
folder name), `description`, plus `paths` and `disable-model-invocation` from
`tools.cursor`. The old `.cursor/rules/<name>.mdc` is not written any more;
`find_legacy_installs` reports it if it is still on disk.
"""

from __future__ import annotations

from pathlib import Path

from ..install import InstallTarget, render_frontmatter, strip_skill_arguments
from ..registry import Skill


def _frontmatter(skill: Skill) -> str:
    """Project a skill into the frontmatter Cursor consumes.

    Legacy `globs` is normalised to `paths` — Cursor documents the rename, so no
    author should have to touch a skill they already wrote. `registry.load_skill`
    enforces `name == directory.name` on the source, and we install into
    `<root>/<skill.name>/`, so emitting `skill.name` here preserves the invariant.
    """
    tools = skill.tools.get("cursor")
    if tools is not None and "globs" in tools and "paths" not in tools:
        # A shallow copy — the source is read-only via MappingProxyType.
        tools = {
            ("paths" if key == "globs" else key): value for key, value in tools.items()
        }
    return render_frontmatter(
        (
            ("name", skill.name),
            ("description", skill.description),
        ),
        tools,
        skill_name=skill.name,
    )


CURSOR = InstallTarget(
    key="cursor",
    label="Cursor",
    root=Path(".cursor") / "skills",
    body=lambda skill: strip_skill_arguments(skill.body),
    frontmatter=_frontmatter,
)
