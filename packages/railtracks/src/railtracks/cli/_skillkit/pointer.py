"""The short skill an assistant loads, pointing at the full one the package ships.

A skill copied into a project goes stale the moment the user upgrades railtracks.
So instead of the full instructions, an install writes a pointer `SKILL.md` that
tells the assistant to run `railtracks skill show <name>`, which prints the
instructions bundled with whatever version is installed. For `railtracks add`, the
full instructions also ship beside it as `reference.md`, stamped with the version
they came from, for when railtracks is missing or too old to have the command.

The Claude Code plugin ships the pointer alone: it is installed before railtracks
usually is, from a repository that doesn't know which release it matches, so it
tells the assistant to install or upgrade railtracks rather than carry a copy.
"""

from __future__ import annotations

from .install import strip_skill_arguments
from .registry import Skill

REFERENCE_FILE = "reference.md"


def _title(skill: Skill) -> str:
    """The skill's first `# ` heading, or its name if it has none."""
    for line in skill.body.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return skill.name


def pointer_body(skill: Skill, version: str | None) -> str:
    """The body of the pointer `SKILL.md` for `skill`.

    Args:
        skill: The bundled skill the pointer stands in for.
        version: The railtracks version `reference.md` is written from, or None
            when no `reference.md` ships beside the pointer (the plugin).

    Returns:
        Markdown that keeps the skill's title and `$ARGUMENTS` line, so targets
        render it the same way they render a full skill body.
    """
    if version is None:
        fallback = "3. If railtracks isn't installed, install it into the project's environment (`pip install railtracks`, or `uv add railtracks`), asking the user first if they haven't asked you to set up the project, then run the command. If it reports `Unknown command: skill`, the installed railtracks is too old: upgrade it (`pip install -U railtracks`) and run it again."
    else:
        fallback = f"3. If railtracks isn't installed, or the command reports `Unknown command: skill`, follow [{REFERENCE_FILE}]({REFERENCE_FILE}) in this folder instead. It was written for railtracks {version}, so tell the user that installing or upgrading railtracks (`pip install -U railtracks`) gets them instructions that match their version."
    return f"""# {_title(skill)}

The user's request: $ARGUMENTS

The instructions for this skill ship with the railtracks package, so they match the version this project has installed. Load them before writing any code:

1. Run `railtracks skill show {skill.name}` and follow what it prints.
2. If the `railtracks` command isn't found, run it with the project's Python environment, for example `uv run railtracks skill show {skill.name}`, or `python -m railtracks.cli skill show {skill.name}` with the project's virtual environment active.
{fallback}
"""


def reference_text(skill: Skill, version: str) -> str:
    """The full instructions for `skill`, stamped with the version they came from.

    Args:
        skill: The bundled skill to render.
        version: The railtracks version the instructions belong to.

    Returns:
        The skill body with `$ARGUMENTS` resolved, since no assistant substitutes
        it outside `SKILL.md`, under a line naming `version`.
    """
    return (
        f"> Written for railtracks {version}. If railtracks is installed, "
        f"`railtracks skill show {skill.name}` prints the instructions for the "
        f"installed version instead.\n\n" + strip_skill_arguments(skill.body) + "\n"
    )


def show_text(skill: Skill, version: str) -> str:
    """What `railtracks skill show <name>` prints: the full instructions for `version`."""
    return (
        f"> Instructions from railtracks {version}, the version installed here.\n\n"
        + strip_skill_arguments(skill.body)
        + "\n"
    )
