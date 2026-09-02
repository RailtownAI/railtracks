"""The record an install leaves behind, so the next one can sync instead of copy.

Every install writes `.railtracks.json` into the skill directory: which skill and
target it was, the railtracks version that wrote it, and a hash per file. The hashes
are what make removal safe — only a file this record names, whose bytes are still
unchanged, may be deleted on a re-install.

`find_legacy_installs` covers skill installs written in the other shapes older
railtracks versions used; it reports them and never removes them.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

MANIFEST_FILE = ".railtracks.json"

MANIFEST_VERSION = 1
"""Schema version of the `.railtracks.json` payload.

`from_json` accepts only this exact value; anything else parses to None and the
install proceeds as if no record existed — prompting before it overwrites, and
removing nothing. That failure direction holds whichever side is newer: an old CLI
will not act on fields it cannot interpret, and a new CLI will not assume an older
record's fields still mean what its own do.

Bump it only when a change would make either of those misread the other: a field
removed or repurposed, a hash algorithm swapped, `path` changing what it is relative
to. Adding an optional field that older readers can ignore does not need a bump,
because they never see it — `from_json` reads named keys and drops the rest.

Bumping costs every installed skill one silent degradation to copy semantics until
its next re-install rewrites the manifest, so it is not free.
"""

_UNKNOWN_VERSION = "unknown"


def package_version() -> str:
    """The installed railtracks version, or `"unknown"` outside an install."""
    # NOTE: read from metadata, not `import railtracks`, to keep the CLI light.
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

        Carries no timestamp, so re-installing an unchanged skill rewrites the same
        bytes and a committed manifest does not churn the diff.
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
        """Parse a manifest, or return None if it is unreadable or not `MANIFEST_VERSION`.

        Never raises: an unusable record degrades to "nothing is known about this
        directory", which costs a prompt rather than blocking the install.
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
    """True if `previous` names `path` and its bytes still match what was recorded.

    The only question that licenses touching a file without asking.
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

    `removable` is recorded, unshipped and byte-for-byte unchanged. `edited` is the
    rest: present but altered since it was written, so not ours to delete.
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
            continue  # already gone
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
# Legacy install detection — report only
# TODO: drop this section once the older install shapes are out of circulation.
# ---------------------------------------------------------------------------

COPILOT_INSTRUCTIONS = Path(".github") / "copilot-instructions.md"
CURSOR_RULES = Path(".cursor") / "rules"


@dataclass(frozen=True)
class LegacyInstall:
    """A skill install found on disk in one of the older shapes.

    Attributes:
        target: The assistant it was installed for.
        path: The file holding it.
        shape: `"region"` for a fenced block inside a file the user also owns,
            `"file"` for a whole file. Each needs a different removal.
        confirmed: Whether the install identifies itself as ours. Copilot's markers
            do; a Cursor `.mdc` cannot, so it is a name match and nothing more.
    """

    target: str
    path: Path
    shape: str
    confirmed: bool

    def advice(self) -> str:
        """What to tell the user, given it will not be removed for them."""
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
    """Find installs of `skill_name` in the older shapes, under `project`.

    Detection only, and it must stay that way: no manifest describes these, and a
    Cursor `.mdc` carries no marker, so a match is never proof the file is ours.
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
        # Matching our generated frontmatter raises confidence; it never licenses a delete.
        found.append(
            LegacyInstall(
                target="Cursor",
                path=rule,
                shape="file",
                confirmed="alwaysApply: false" in text,
            )
        )

    return found
