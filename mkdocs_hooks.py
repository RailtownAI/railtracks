"""MkDocs hooks for generating derived documentation files."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def _generate_api_reference(repo_root: Path) -> None:
    """Generate the API reference site with pdoc."""

    output_dir = repo_root / "docs" / "api_reference"
    subprocess.run(
        [
            sys.executable,
            "-m",
            "pdoc",
            "packages/railtracks/src/railtracks",
            "--output-dir",
            str(output_dir),
            "-d",
            "google",
            "--include-undocumented",
            "--logo",
            "https://raw.githubusercontent.com/RailtownAI/railtracks/main/docs/assets/logo.svg",
        ],
        check=True,
        cwd=repo_root,
    )


def on_pre_build(config, **kwargs):
    """Regenerate generated docs before MkDocs serves or builds the site."""

    repo_root = Path(__file__).resolve().parent
    _generate_api_reference(repo_root)
