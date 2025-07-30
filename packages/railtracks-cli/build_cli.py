#!/usr/bin/env python3
"""
Build script for the railtracks CLI package in the monorepo.
This script helps build and install the CLI package locally for development.
"""

import subprocess
import sys
from pathlib import Path


def run_command(cmd, cwd=None):
    """Run a command and return the result."""
    print(f"Running: {cmd}")
    if cwd:
        print(f"Working directory: {cwd}")

    result = subprocess.run(cmd, shell=True, cwd=cwd, capture_output=True, text=True)

    if result.returncode != 0:
        print(f"Error: {result.stderr}")
        return False

    print(f"Success: {result.stdout}")
    return True


def main():
    """Build the CLI package."""
    # Get the project root directory
    project_root = Path(__file__).parent.parent
    cli_dir = project_root / "railtracks-cli"

    if not cli_dir.exists():
        print(f"Error: CLI directory not found at {cli_dir}")
        sys.exit(1)

    print("Building railtracks CLI package...")

    # Build the CLI package
    if not run_command("python -m build", cwd=cli_dir):
        print("Failed to build CLI package")
        sys.exit(1)

    print("CLI package built successfully!")
    print("\nTo install the CLI package locally for development:")
    print("pip install -e railtracks-cli/")
    print("\nTo install the main package with CLI:")
    print("pip install -e .[cli]")


if __name__ == "__main__":
    main()
