"""Installing a skill directory into an assistant's native layout.

An `InstallTarget` supplies the two things that differ per assistant — the root path
it reads skills from, and the projection that renders `SKILL.md` for it. Concrete
targets live in `providers/`, one file per assistant; adding another one is a copy of
one of those files. This module owns the workflow: copy the directory, drop what a
previous install left and this one does not ship, and record the result.
"""

from __future__ import annotations

import shutil
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

import yaml

from ..io import confirm_overwrite, print_status, print_success, print_warning
from .manifest import (
    find_legacy_installs,
    is_ours_unmodified,
    prune,
    read_record,
    record_for,
    stale_files,
    version_skew,
    write_record,
)
from .registry import SKILL_FILE, Skill


def strip_skill_arguments(content: str) -> str:
    """Resolve the `$ARGUMENTS` placeholder for targets that never substitute it.

    Claude Code is the only target with an argument-hint field and documented
    `$ARGUMENTS` substitution, so it is the only one that gets the placeholder. For
    every other target the placeholder would ship to the model literally, so we drop
    a whole line whose sole purpose is to introduce the argument and reword an
    inline mention as "the request".

    Lives on the projection so a handler cannot skip it.
    """
    kept: list[str] = []
    drop_next_blank = False
    for line in content.splitlines():
        if drop_next_blank and not line.strip():
            drop_next_blank = False
            continue
        drop_next_blank = False

        if "$ARGUMENTS" not in line:
            kept.append(line)
            continue

        # Drop the whole intro line (and its trailing blank); reword inline mentions in place.
        if line.rstrip().endswith(": $ARGUMENTS"):
            drop_next_blank = bool(kept) and not kept[-1].strip()
            continue

        kept.append(
            line.replace("`$ARGUMENTS`", "the request").replace(
                "$ARGUMENTS", "the request"
            )
        )
    return "\n".join(kept)


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
        body: Renders the Markdown body the target receives.
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

    `ordered` is emitted verbatim in the given order; a value of None omits its key.
    `extra` is the target's `tools.<assistant>` block, dumped through YAML so that
    author-written values and unknown keys survive unchanged.
    """
    lines = [f"{key}: {value}\n" for key, value in ordered if value is not None]

    emitted = {key for key, value in ordered if value is not None}
    passthrough = {}
    for key, value in (extra or {}).items():
        # A duplicate key would be resolved silently by the reader, so warn instead.
        if key in emitted:
            print_warning(
                f"skill '{skill_name}': '{key}' in the tools block is ignored; "
                f"the skill's own '{key}' is used instead."
            )
            continue
        passthrough[key] = value

    # Force block style: a one-key flow map after block-style lines is ambiguous YAML.
    rendered_extra = (
        yaml.safe_dump(
            passthrough, default_flow_style=False, sort_keys=False, allow_unicode=True
        )
        if passthrough
        else ""
    )
    return "---\n" + "".join(lines) + rendered_extra + "---\n\n"


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
    one does not, and records the result for the next install.

    Prompts before touching any file it cannot prove was written by a previous
    install and left untouched, unless `force` is set; exits if the user declines.
    """
    destination = target.root / skill.name
    planned = _planned_files(skill, destination)
    previous = read_record(destination)

    # Report legacy Copilot/Cursor installs the new handler will not touch.
    for legacy in find_legacy_installs(skill.name):
        print_warning(legacy.advice())

    skew = version_skew(previous)
    if skew:
        print_status(skew)

    at_risk = [
        path
        for path, _ in planned
        if path.exists() and not is_ours_unmodified(path, destination, previous)
    ]
    if at_risk and not force:
        # One clash reads better named directly; several, as the directory they share.
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
