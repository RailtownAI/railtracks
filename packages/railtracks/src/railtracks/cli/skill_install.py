"""Installing a discovered skill directory into an assistant's native layout.

Every assistant that supports skill *directories* takes the same install: copy
``SKILL.md`` plus its supporting files to ``<root>/<name>/``, with the skill's
frontmatter projected into the keys that assistant actually consumes. Only two
things differ per target, so those two are the parameters and
`install_skill_directory` is the shared body:

* **the root path** — ``.claude/skills``, ``.agents/skills``, ``.github/skills``,
  ``.cursor/skills``. Each assistant gets its own native path even where the paths
  cross-read, so that one ``railtracks add`` maps to exactly one directory on disk.
* **the projection** — how the skill's metadata and body become the file the target
  reads. Both halves live here rather than in a handler: the frontmatter half
  because targets consume different key sets, and the body half because
  ``$ARGUMENTS`` is substituted only by Claude Code and must be resolved away for
  everyone else. A handler that copies ``skill.body`` straight to disk reintroduces
  that bug for its target.

Claude Code is the first target through here. The remaining three wait on the
install manifest, which owns removing the legacy installs they are migrating from.

Re-installing is a **sync**, not a copy: `skill_manifest` records what each install
wrote, so the next one can remove a supporting file we shipped before and no longer
do. Removal is gated on proof — the file must be one we recorded *and* still be
byte-for-byte what we left — so a file somebody edited is reported and kept.

**Authoring constraint for skills that ship supporting files:** Claude Code reads a
supporting file only when ``SKILL.md`` links it, while Copilot auto-discovers the
whole directory. A skill written for auto-discovery therefore silently
under-delivers on Claude Code, so every supporting file must be linked from the
body by explicit relative path. That is the strict case, and it is free for every
other target.
"""

from __future__ import annotations

import shutil
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

import yaml

from .io import confirm_overwrite, print_status, print_success, print_warning
from .skill_manifest import (
    is_ours_unmodified,
    prune,
    read_record,
    record_for,
    stale_files,
    version_skew,
    write_record,
)
from .skills_registry import SKILL_FILE, Skill


@dataclass(frozen=True)
class InstallTarget:
    """One assistant's directory install: where it reads, and what it reads.

    Attributes:
        key: The assistant's name as `railtracks add <key>:<skill>` spells it, and as
            the manifest records it.
        label: The assistant's display name, for CLI output.
        root: Directory holding one sub-directory per installed skill, relative to
            the project the user is running in.
        frontmatter: Renders the skill's metadata into the target's frontmatter
            block, `---` delimiters and trailing blank line included.
        body: Renders the Markdown body the target receives. Only Claude Code
            passes it through unchanged; see the module docstring.
    """

    key: str
    label: str
    root: Path
    frontmatter: Callable[[Skill], str]
    body: Callable[[Skill], str]


def render_frontmatter(
    ordered: Sequence[tuple[str, Any]],
    extra: Mapping[str, Any] | None = None,
    *,
    skill_name: str = "",
) -> str:
    """Render a frontmatter block from projected keys plus a target's `tools:` block.

    `ordered` carries the keys every install of this target emits, in the order it
    emits them, and is rendered verbatim — a value of None omits its key entirely,
    which is how an absent `argument-hint` avoids shipping the literal "None".
    `extra` is the target's own `tools.<assistant>` block: rendered through YAML
    rather than by hand, because its values are whatever the skill author wrote and
    unknown keys have to survive unchanged. Leaf collections stay in flow style, so a
    hand-written `allowed-tools: [Read, Edit]` comes back out the way it went in.
    """
    lines = [f"{key}: {value}\n" for key, value in ordered if value is not None]

    emitted = {key for key, value in ordered if value is not None}
    passthrough = {}
    for key, value in (extra or {}).items():
        # A duplicate key would be silently resolved by whichever YAML parser reads
        # the result, so the projected key wins and the collision is reported.
        if key in emitted:
            print_warning(
                f"skill '{skill_name}': '{key}' in the tools block is ignored; "
                f"the skill's own '{key}' is used instead."
            )
            continue
        passthrough[key] = value

    rendered_extra = (
        yaml.safe_dump(
            passthrough, default_flow_style=None, sort_keys=False, allow_unicode=True
        )
        if passthrough
        else ""
    )
    return "---\n" + "".join(lines) + rendered_extra + "---\n\n"


def _quote(value: str) -> str:
    """Emit a string as a double-quoted YAML scalar."""
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def claude_frontmatter(skill: Skill) -> str:
    """Project a skill into the frontmatter Claude Code consumes.

    `name` and `description` are Claude-native keys already, so this is close to a
    verbatim copy — which is the point of building the reference handler here.
    `argument-hint` is Claude-only (no other target has the field or a documented
    substitution), and `tools.claude` carries the rest: `allowed-tools`, `paths`,
    `disable-model-invocation`, and anything a later Claude version adds.
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
    # Claude Code is the one target that substitutes $ARGUMENTS, so it is the one
    # target whose body ships as authored.
    body=lambda skill: skill.body,
    frontmatter=claude_frontmatter,
)


def _planned_files(skill: Skill, destination: Path) -> list[tuple[Path, Path | None]]:
    """Every file this install writes, as (destination, source or None for SKILL.md)."""
    planned: list[tuple[Path, Path | None]] = [(destination / SKILL_FILE, None)]
    planned += [
        (destination / relative, skill.directory / relative)
        for relative in skill.supporting_files
    ]
    return planned


def install_skill_directory(
    skill: Skill, target: InstallTarget, force: bool = False
) -> list[Path]:
    """Sync `skill` into `target` and return the files written, in write order.

    Writes what the package ships now, removes what a previous install wrote and this
    one does not, and records the result so the *next* install can do the same.

    Prompts before touching anything it cannot prove is ours and unmodified, unless
    `force` is set, and exits without writing if the user declines. A file we wrote
    and nobody has edited is not worth a prompt — re-running the command would
    otherwise nag about its own output, which only teaches people to reach for
    `--force` and lose the protection where it matters.
    """
    destination = target.root / skill.name
    planned = _planned_files(skill, destination)
    previous = read_record(destination)

    skew = version_skew(previous)
    if skew:
        print_status(skew)

    at_risk = [
        path
        for path, _ in planned
        if path.exists() and not is_ours_unmodified(path, destination, previous)
    ]
    if at_risk and not force:
        # One clash reads better named directly; several read better as the
        # directory they share.
        if not confirm_overwrite(at_risk[0] if len(at_risk) == 1 else destination):
            print_status("Aborted.")
            sys.exit(0)

    written: list[Path] = []
    for path, source in planned:
        path.parent.mkdir(parents=True, exist_ok=True)
        if source is None:
            path.write_text(
                target.frontmatter(skill) + target.body(skill), encoding="utf-8"
            )
        else:
            shutil.copy2(source, path)
        written.append(path)

    removable, edited = stale_files(destination, previous, written)
    prune(destination, removable)
    for path in removable:
        print_status(f"Removed '{path}', no longer part of '{skill.name}'.")
    for path in edited:
        print_warning(
            f"Kept '{path}': '{skill.name}' no longer ships it, but it has been "
            f"edited since we wrote it. Delete it by hand if you do not want it."
        )

    write_record(destination, record_for(skill.name, target.key, destination, written))

    extras = len(written) - 1
    suffix = (
        f" (+{extras} supporting file{'' if extras == 1 else 's'})" if extras else ""
    )
    print_success(
        f"Installed '{skill.name}' for {target.label} -> {written[0]}{suffix}"
    )
    return written
