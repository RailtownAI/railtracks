"""Generate the Claude Code plugin's skills from the bundled CLI skills.

The plugin under `plugins/railtracks/` ships every bundled skill in
`packages/railtracks/src/railtracks/cli/skills/`, rendered exactly as
`railtracks add claude:<skill>` writes it, plus any supporting files the skill ships.
Never edit `plugins/railtracks/skills/` by hand; run this script instead.

Usage:
    python scripts/sync_plugin_skills.py           # rewrite plugins/railtracks/skills/
    python scripts/sync_plugin_skills.py --check   # exit 1 if it is out of date
"""

import shutil
import sys
from pathlib import Path

from railtracks.cli._skillkit import CLAUDE, discover_skills

SKILLS_DIR = (
    Path(__file__).resolve().parent.parent / "plugins" / "railtracks" / "skills"
)


def expected_files() -> dict[Path, bytes]:
    """Every file the plugin's skills directory should hold, relative to it."""
    files: dict[Path, bytes] = {}
    for skill in discover_skills().values():
        files[Path(skill.name, "SKILL.md")] = (
            CLAUDE.frontmatter(skill) + CLAUDE.body(skill)
        ).encode("utf-8")
        for relative in skill.supporting_files:
            files[Path(skill.name, relative)] = (
                skill.directory / relative
            ).read_bytes()
    return files


def actual_files() -> dict[Path, bytes]:
    """Every file currently in the plugin's skills directory, relative to it."""
    if not SKILLS_DIR.is_dir():
        return {}
    return {
        path.relative_to(SKILLS_DIR): path.read_bytes()
        for path in SKILLS_DIR.rglob("*")
        if path.is_file()
    }


def main() -> None:
    expected = expected_files()

    if "--check" in sys.argv[1:]:
        actual = actual_files()
        differing = sorted(
            path
            for path in expected.keys() | actual.keys()
            if expected.get(path) != actual.get(path)
        )
        if differing:
            print("plugins/railtracks/skills/ is out of date with the bundled skills:")
            for path in differing:
                print(f"  {path}")
            print("\nRun: python scripts/sync_plugin_skills.py")
            sys.exit(1)
        print("plugins/railtracks/skills/ is in sync with the bundled skills.")
        return

    shutil.rmtree(SKILLS_DIR, ignore_errors=True)
    for relative, content in expected.items():
        path = SKILLS_DIR / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
    print(f"Wrote {len(expected)} file(s) to plugins/railtracks/skills/.")


if __name__ == "__main__":
    main()
