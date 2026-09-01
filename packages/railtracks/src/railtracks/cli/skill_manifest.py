"""What an install left on disk, so a re-install can be a sync rather than a copy.

A plain directory copy cannot remove anything. When a skill drops a `references/`
page, the old page stays in the user's repo and the assistant goes on reading it —
the failure this module exists to prevent. Removing it safely needs one thing a copy
never has: **proof that we wrote the file and that nobody has touched it since.**
That is the whole reason each record carries a per-file hash rather than just a path.

One manifest per installed skill, written into the skill directory itself as
`.railtracks.json`. The record and the files it describes are therefore created,
overwritten and deleted together, so a manifest can never outlive its files or
describe a directory somebody removed by hand. Every target uses the same shape,
because every target's modern install is the same shape: `<root>/<name>/SKILL.md`
plus supporting files.

**Legacy installs are deliberately not in here.** Copilot's marker block in
`copilot-instructions.md` and Cursor's `.cursor/rules/<name>.mdc` are shapes we no
longer write (D10), so no manifest we produce will ever record one, and the ones
already on users' disks predate manifests entirely — there is nothing to look up.
They get `find_legacy_installs`: detection that reports and never removes, because
a `.mdc` carries nothing that says railtracks and deleting on a filename guess
eventually eats a rule someone hand-wrote. That detection is time-boxed to one minor
cycle after the directory install ships, and then deleted along with this comment.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

MANIFEST_FILE = ".railtracks.json"

# Bumped only when an older CLI could misread a newer record. A record whose version
# we do not recognise is treated as absent: we will overwrite files we cannot prove
# are ours, but we will never delete one on a guess.
MANIFEST_VERSION = 1

_UNKNOWN_VERSION = "unknown"


def package_version() -> str:
    """The installed railtracks version, or `"unknown"` outside an install.

    Read from package metadata rather than importing `railtracks`, which would pull
    the whole SDK into a CLI that deliberately stays light.
    """
    try:
        return version("railtracks")
    except PackageNotFoundError:
        return _UNKNOWN_VERSION


def file_digest(path: Path) -> str:
    """The SHA-256 of `path`'s bytes."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


@dataclass(frozen=True)
class InstalledFile:
    """One file an install wrote: where it went, and what we left there."""

    path: str  # relative to the skill directory, POSIX separators
    sha256: str


@dataclass(frozen=True)
class InstallRecord:
    """What one `railtracks add` wrote for one skill and one target."""

    skill: str
    target: str
    package_version: str
    files: tuple[InstalledFile, ...]

    def to_json(self) -> str:
        """Serialise deterministically.

        No timestamp, deliberately: re-installing an unchanged skill then produces a
        byte-identical manifest, so a committed manifest does not churn the diff every
        time somebody re-runs the command.
        """
        return (
            json.dumps(
                {
                    "manifest_version": MANIFEST_VERSION,
                    "skill": self.skill,
                    "target": self.target,
                    "package_version": self.package_version,
                    "files": [{"path": f.path, "sha256": f.sha256} for f in self.files],
                },
                indent=2,
            )
            + "\n"
        )

    @classmethod
    def from_json(cls, text: str) -> InstallRecord | None:
        """Parse a manifest, or return None if it is unreadable or too new.

        Tolerant on purpose. A corrupt or future manifest must degrade to "we know
        nothing about this directory", which costs an overwrite prompt, rather than
        raising and blocking the install or licensing a delete.
        """
        try:
            raw = json.loads(text)
        except (json.JSONDecodeError, UnicodeDecodeError):
            return None
        if not isinstance(raw, dict) or raw.get("manifest_version") != MANIFEST_VERSION:
            return None
        try:
            files = tuple(
                InstalledFile(path=str(entry["path"]), sha256=str(entry["sha256"]))
                for entry in raw["files"]
            )
            return cls(
                skill=str(raw["skill"]),
                target=str(raw["target"]),
                package_version=str(raw["package_version"]),
                files=files,
            )
        except (KeyError, TypeError):
            return None


def read_record(destination: Path) -> InstallRecord | None:
    """Read the manifest in `destination`, or None if there is not a usable one."""
    manifest = destination / MANIFEST_FILE
    if not manifest.is_file():
        return None
    try:
        return InstallRecord.from_json(manifest.read_text(encoding="utf-8"))
    except OSError:
        return None


def write_record(destination: Path, record: InstallRecord) -> Path:
    """Write `record` into `destination` and return the manifest's path."""
    manifest = destination / MANIFEST_FILE
    manifest.write_text(record.to_json(), encoding="utf-8")
    return manifest


def record_for(
    skill_name: str, target: str, destination: Path, written: list[Path]
) -> InstallRecord:
    """Describe an install that just wrote `written` into `destination`."""
    return InstallRecord(
        skill=skill_name,
        target=target,
        package_version=package_version(),
        files=tuple(
            InstalledFile(
                path=path.relative_to(destination).as_posix(),
                sha256=file_digest(path),
            )
            for path in written
        ),
    )


def is_ours_unmodified(
    path: Path, destination: Path, previous: InstallRecord | None
) -> bool:
    """True if `previous` says we wrote `path` and its bytes still match.

    The one question that licenses acting on a file without asking. A file we never
    recorded, or one whose bytes have moved since, answers no.
    """
    if previous is None:
        return False
    relative = path.relative_to(destination).as_posix()
    recorded = next((f for f in previous.files if f.path == relative), None)
    if recorded is None:
        return False
    try:
        return file_digest(path) == recorded.sha256
    except OSError:
        return False


def stale_files(
    destination: Path, previous: InstallRecord | None, keeping: list[Path]
) -> tuple[list[Path], list[Path]]:
    """Split what the last install wrote and this one does not into (removable, edited).

    `removable` is every file we recorded, no longer ship, and can still prove is
    byte-for-byte what we left. `edited` is the rest — present but changed since we
    wrote it, so somebody has put work into it and it is not ours to delete.
    """
    if previous is None:
        return [], []

    keep = {path.relative_to(destination).as_posix() for path in keeping}
    removable: list[Path] = []
    edited: list[Path] = []
    for recorded in previous.files:
        if recorded.path in keep:
            continue
        path = destination / recorded.path
        if not path.is_file():
            continue  # already gone; nothing to do and nothing to report
        if is_ours_unmodified(path, destination, previous):
            removable.append(path)
        else:
            edited.append(path)
    return removable, edited


def prune(destination: Path, paths: list[Path]) -> None:
    """Delete `paths`, then any directories under `destination` they leave empty."""
    for path in paths:
        path.unlink(missing_ok=True)
    for path in paths:
        parent = path.parent
        while parent != destination and destination in parent.parents:
            try:
                parent.rmdir()
            except OSError:
                break  # not empty, or gone already
            parent = parent.parent


def version_skew(previous: InstallRecord | None) -> str | None:
    """A message if the install on disk came from a different railtracks, else None."""
    if previous is None:
        return None
    current = package_version()
    if previous.package_version in (current, _UNKNOWN_VERSION):
        return None
    if current == _UNKNOWN_VERSION:
        return None
    return (
        f"'{previous.skill}' was installed from railtracks "
        f"{previous.package_version}; this is {current}."
    )


# ---------------------------------------------------------------------------
# Legacy install detection — report only, and time-boxed (D10)
# ---------------------------------------------------------------------------

COPILOT_INSTRUCTIONS = Path(".github") / "copilot-instructions.md"
CURSOR_RULES = Path(".cursor") / "rules"


@dataclass(frozen=True)
class LegacyInstall:
    """An install in a shape we no longer write, found on disk.

    Attributes:
        target: The assistant it was installed for.
        path: The file holding it.
        shape: `"region"` for a fenced block inside a file the user also owns,
            `"file"` for a whole file. The two need different removals, which is why
            the distinction is recorded rather than inferred at the call site.
        confirmed: Whether the install identifies itself as ours. Copilot's markers
            do; a Cursor `.mdc` never can, so it is a name match and nothing more.
    """

    target: str
    path: Path
    shape: str
    confirmed: bool

    def advice(self) -> str:
        """What to tell the user, given we will not remove it for them."""
        if self.shape == "region":
            return (
                f"{self.path} still carries a legacy {self.target} install of this "
                f"skill between its '<!-- railtracks:' markers. It is injected into "
                f"every request and will not be updated again — delete that block."
            )
        confidence = (
            "It looks like ours"
            if self.confirmed
            else "It matches the name of a bundled skill, but nothing in the file "
            "identifies it, so it may be yours"
        )
        return (
            f"{self.path} is a legacy {self.target} install of this skill. "
            f"{confidence} — review it and delete it if you no longer want it; "
            f"it will not be updated again."
        )


def find_legacy_installs(
    skill_name: str, project: Path | None = None
) -> list[LegacyInstall]:
    """Find installs of `skill_name` in shapes this version no longer writes.

    Detection only. Nothing here removes anything, and nothing should start to:
    these installs predate the manifest, so there is no record saying we wrote them,
    and Cursor's file carries no marker of its own. A name match is a reason to tell
    the user, never a reason to delete their file.
    """
    root = Path(".") if project is None else project
    found: list[LegacyInstall] = []

    instructions = root / COPILOT_INSTRUCTIONS
    if instructions.is_file():
        try:
            text = instructions.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            text = ""
        if f"<!-- railtracks:{skill_name}:start -->" in text:
            found.append(
                LegacyInstall(
                    target="Copilot",
                    path=instructions,
                    shape="region",
                    confirmed=True,
                )
            )

    rule = root / CURSOR_RULES / f"{skill_name}.mdc"
    if rule.is_file():
        try:
            text = rule.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            text = ""
        # The strongest signal available: the frontmatter our generator emitted. It
        # raises confidence for the report; it never authorises a delete.
        found.append(
            LegacyInstall(
                target="Cursor",
                path=rule,
                shape="file",
                confirmed="alwaysApply: false" in text,
            )
        )

    return found
