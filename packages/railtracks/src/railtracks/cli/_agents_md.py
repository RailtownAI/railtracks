"""`railtracks agents-md`: keep a managed Railtracks block in a project's `AGENTS.md`.

The block sits between `BEGIN_MARKER` and `END_MARKER`. A re-run replaces only what
is between them and leaves the rest of the file byte for byte. `CLAUDE.md` gets an
`@AGENTS.md` import, since Claude Code skips `AGENTS.md` once a `CLAUDE.md` exists.
"""

from __future__ import annotations

from collections.abc import Callable
from enum import Enum
from pathlib import Path

from ._skillkit.manifest import package_version

BEGIN_MARKER = "<!-- BEGIN:railtracks-agent-rules -->"
END_MARKER = "<!-- END:railtracks-agent-rules -->"
CLAUDE_IMPORT = "@AGENTS.md"

TEMPLATE_PATH = Path(__file__).parent / "agents_md" / "railtracks-agent-rules.md"
_VERSION_PLACEHOLDER = "{railtracks_version}"


class FileChange(Enum):
    """What happened to one file."""

    CREATED = "Created"
    UPDATED = "Updated"
    UNCHANGED = "Unchanged"


class MalformedBlockError(ValueError):
    """`AGENTS.md` has one marker without the other, or them in the wrong order."""


def render_block(version: str | None = None) -> str:
    """The full managed block, markers included, stamped with `version`.

    Args:
        version: The railtracks version to stamp; defaults to the installed one.
    Returns:
        The block text, ending in a newline.
    """
    body = TEMPLATE_PATH.read_text(encoding="utf-8")
    body = body.replace(_VERSION_PLACEHOLDER, version or package_version())
    return f"{BEGIN_MARKER}\n{body.rstrip()}\n{END_MARKER}\n"


def upsert_block(existing: str, block: str) -> str:
    """Put `block` into `existing`, replacing a previous block if there is one.

    Args:
        existing: The current file contents.
        block: The rendered block from `render_block`.
    Returns:
        The new file contents.
    Raises:
        MalformedBlockError: If only one marker is present, or END comes first.
    """
    start = existing.find(BEGIN_MARKER)
    end = existing.find(END_MARKER)
    if start == -1 and end == -1:
        if not existing:
            return block
        separator = "\n" if existing.endswith("\n") else "\n\n"
        return f"{existing}{separator}{block}"
    if start == -1 or end == -1 or end < start:
        raise MalformedBlockError(
            f"Found an unmatched {BEGIN_MARKER} / {END_MARKER} pair."
        )
    end += len(END_MARKER)
    # The rendered block carries its own trailing newline; absorb the old one.
    if existing.startswith("\n", end):
        end += 1
    return existing[:start] + block + existing[end:]


def ensure_claude_import(existing: str) -> str:
    """`existing` with an `@AGENTS.md` line appended, unless it already has one.

    Args:
        existing: The current `CLAUDE.md` contents.
    Returns:
        The new file contents.
    """
    if any(line.strip() == CLAUDE_IMPORT for line in existing.splitlines()):
        return existing
    if not existing:
        return f"{CLAUDE_IMPORT}\n"
    separator = "\n" if existing.endswith("\n") else "\n\n"
    return f"{existing}{separator}{CLAUDE_IMPORT}\n"


def _write(path: Path, transform: Callable[[str], str]) -> FileChange:
    """Apply `transform` to `path`'s text and write it back only if it changed."""
    # Bytes in and out, so line endings outside the block survive untouched.
    existed = path.exists()
    before = path.read_bytes().decode("utf-8") if existed else ""
    after = transform(before)
    if existed and after == before:
        return FileChange.UNCHANGED
    path.write_bytes(after.encode("utf-8"))
    return FileChange.UPDATED if existed else FileChange.CREATED


def write_agents_md(
    root: Path, version: str | None = None
) -> list[tuple[Path, FileChange]]:
    """Upsert the block into `root/AGENTS.md` and make `root/CLAUDE.md` import it.

    Args:
        root: The project root.
        version: The railtracks version to stamp; defaults to the installed one.
    Returns:
        Each file touched, with what happened to it.
    Raises:
        MalformedBlockError: If `AGENTS.md` has a broken marker pair.
    """
    block = render_block(version)
    agents = root / "AGENTS.md"
    claude = root / "CLAUDE.md"
    return [
        (agents, _write(agents, lambda text: upsert_block(text, block))),
        (claude, _write(claude, ensure_claude_import)),
    ]
