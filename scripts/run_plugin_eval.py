"""Run the Claude Code plugin's eval suite against the full skill instructions.

`claude plugin eval` runs every case in a fresh sandbox with no railtracks installed
and limited network, so the real plugin's pointer skills can't reach
`railtracks skill show` there. This builds a throwaway copy of the plugin whose skills
hold the full instructions that command prints, copies in the cases from
`plugins/railtracks/evals/`, and runs the eval against it. Each case runs with and
without the plugin, so the report shows what the instructions change.

Usage:
    python scripts/run_plugin_eval.py [claude plugin eval options...]
    python scripts/run_plugin_eval.py --case two-tools --runs 1

Results are copied back to `plugins/railtracks/evals/results/` (git-ignored).
"""

import dataclasses
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from railtracks.cli._skillkit import CLAUDE, discover_skills, strip_skill_arguments

PLUGIN_DIR = Path(__file__).resolve().parent.parent / "plugins" / "railtracks"
EVALS_DIR = PLUGIN_DIR / "evals"


def build_full_plugin(root: Path) -> Path:
    """Write a copy of the plugin with full-instruction skills under `root`."""
    plugin = root / "railtracks"
    shutil.copytree(PLUGIN_DIR / ".claude-plugin", plugin / ".claude-plugin")
    for skill in discover_skills().values():
        full = dataclasses.replace(skill, body=strip_skill_arguments(skill.body))
        path = plugin / "skills" / skill.name / "SKILL.md"
        path.parent.mkdir(parents=True)
        path.write_text(CLAUDE.frontmatter(full) + CLAUDE.body(full), encoding="utf-8")
    shutil.copytree(
        EVALS_DIR, plugin / "evals", ignore=shutil.ignore_patterns("results")
    )
    return plugin


def main() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        plugin = build_full_plugin(Path(tmp))
        command = [
            "claude",
            "plugin",
            "eval",
            str(plugin),
            "--trust-plugin",
            "--allow-tools",
            "Write",
            "Edit",
            *sys.argv[1:],
        ]
        code = subprocess.call(command)
        results = plugin / "evals" / "results"
        if results.is_dir():
            shutil.copytree(results, EVALS_DIR / "results", dirs_exist_ok=True)
    sys.exit(code)


if __name__ == "__main__":
    main()
