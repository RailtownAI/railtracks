#!/usr/bin/env python3
"""
Publish Railtracks packages to Azure Artifacts.

This script replicates the GitHub Actions release workflow logic for publishing
both railtracks and railtracks-cli packages to Azure Artifacts.

By default, runs in DRY-RUN mode (shows what would be done without publishing).
Use --publish flag to actually publish packages.

Usage:
    python scripts/publish_to_azure_artifacts.py <version>          # Dry run (default)
    python scripts/publish_to_azure_artifacts.py <version> --publish  # Actually publish

Example:
    python scripts/publish_to_azure_artifacts.py 1.0.0              # Test the process
    python scripts/publish_to_azure_artifacts.py v1.0.0 --publish   # Actually publish
"""

import argparse
import os
import re
import subprocess
import sys
from pathlib import Path

# Load .env file - required for Azure PAT
try:
    from dotenv import load_dotenv

    # Check if .env file exists
    env_file = Path(__file__).parent.parent / ".env"
    if not env_file.exists():
        print("Error: .env file not found in project root")
        print("Please create a .env file with AZURE_ARTIFACTS_PAT=your_token")
        sys.exit(1)

    load_dotenv(env_file)
except ImportError:
    print("Error: python-dotenv is required but not installed.")
    print("Install it with: pip install python-dotenv")
    sys.exit(1)


def run_command(cmd, cwd=None, check=True, capture_output=True):
    """Run a command and return the result."""
    print(f"Running: {cmd}")
    if cwd:
        print(f"Working directory: {cwd}")

    try:
        result = subprocess.run(
            cmd,
            shell=True,
            cwd=cwd,
            capture_output=capture_output,
            text=True,
            check=check,
        )

        if capture_output and result.stdout:
            print(f"Output: {result.stdout}")

        return result
    except subprocess.CalledProcessError as e:
        print(f"Error: {e}")
        if e.stderr:
            print(f"Stderr: {e.stderr}")
        if check:
            sys.exit(1)
        return e


def normalize_version(version):
    """Normalize version number by removing 'v' prefix if present."""
    version_cleaned = version.lstrip("v")
    print(f"Normalized version: {version_cleaned}")
    return version_cleaned


def update_version_in_file(file_path, version):
    """Update __version__ in a Python file."""
    print(f"Updating version in {file_path}")

    # Check if file exists
    if not file_path.exists():
        print(f"Error: File not found: {file_path}")
        sys.exit(1)

    try:
        with open(file_path, "r") as f:
            content = f.read()

        # Replace __version__ = "..." with new version
        pattern = r'__version__ = "[^"]*"'
        replacement = f'__version__ = "{version}"'

        new_content = re.sub(pattern, replacement, content)

        # Verify that the replacement actually happened
        if new_content == content:
            print(f"Error: Could not find __version__ line in {file_path}")
            sys.exit(1)

        with open(file_path, "w") as f:
            f.write(new_content)

        print(f"Updated {file_path} to version {version}")
    except Exception as e:
        print(f"Error updating version in {file_path}: {e}")
        sys.exit(1)


def publish_package(package_dir, package_name, azure_pat):
    """Publish a package to Azure Artifacts using flit."""
    print(f"\n{'=' * 50}")
    print(f"Publishing {package_name}")
    print(f"{'=' * 50}")

    # Set environment variables for Azure Artifacts
    env = os.environ.copy()
    env.update(
        {
            "FLIT_INDEX_URL": "https://pkgs.dev.azure.com/railtownai/ML/_packaging/railtownai_rc/pypi/upload/",
            "FLIT_USERNAME": "AZURE",
            "FLIT_PASSWORD": azure_pat,
        }
    )

    # Run flit publish
    cmd = "flit publish"
    print(f"Running: {cmd}")
    print(f"Working directory: {package_dir}")

    try:
        result = subprocess.run(
            cmd,
            shell=True,
            cwd=package_dir,
            env=env,
            check=True,
            capture_output=True,
            text=True,
        )
        print(f"Successfully published {package_name}")
        if result.stdout:
            print(f"Output: {result.stdout}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"Failed to publish {package_name}")
        print(f"Error: {e}")
        if e.stderr:
            print(f"Stderr: {e.stderr}")
        return False


def validate_version(version):
    """Validate version format."""
    # Check if version follows semantic versioning (MAJOR.MINOR.PATCH)
    pattern = r"^\d+\.\d+\.\d+$"
    if not re.match(pattern, version):
        print(
            f"Error: Invalid version format '{version}'. Expected format: MAJOR.MINOR.PATCH (e.g., '1.0.0')"
        )
        sys.exit(1)


def validate_azure_pat(azure_pat):
    """Validate Azure PAT format."""
    if not azure_pat:
        print("Error: AZURE_ARTIFACTS_PAT is not defined in .env file")
        print("Please add AZURE_ARTIFACTS_PAT=your_token to your .env file")
        sys.exit(1)

    # Basic validation - Azure PATs are typically long strings
    if len(azure_pat) < 20:
        print(
            "Error: AZURE_ARTIFACTS_PAT appears to be too short. Please check your token."
        )
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        description="Publish Railtracks packages to Azure Artifacts",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "version", help="Version to publish (e.g., '1.0.0' or 'v1.0.0')"
    )
    parser.add_argument(
        "--publish",
        action="store_true",
        help="Actually publish packages (default is dry-run mode)",
    )

    args = parser.parse_args()

    # Get Azure PAT from environment (loaded from .env file)
    azure_pat = os.environ.get("AZURE_ARTIFACTS_PAT")

    # Validate Azure PAT
    validate_azure_pat(azure_pat)

    # Normalize version
    version = normalize_version(args.version)

    # Validate version format
    validate_version(version)

    # Get project root
    project_root = Path(__file__).parent.parent
    railtracks_dir = project_root / "packages" / "railtracks"
    railtracks_cli_dir = project_root / "packages" / "railtracks-cli"

    # Validate package directories exist
    if not railtracks_dir.exists():
        print(f"Error: railtracks package directory not found at {railtracks_dir}")
        sys.exit(1)

    if not railtracks_cli_dir.exists():
        print(
            f"Error: railtracks-cli package directory not found at {railtracks_cli_dir}"
        )
        sys.exit(1)

    print(f"Project root: {project_root}")
    print(f"Publishing version: {version}")

    if not args.publish:
        print("\n✨ DRY RUN MODE - No packages will be published ✨")
        print(f"Would update version to {version} in:")
        print(f"  - {railtracks_dir}/src/railtracks/__init__.py")
        print(f"  - {railtracks_cli_dir}/src/railtracks_cli/__init__.py")
        print(f"Would publish packages from:")  # noqa: F541
        print(f"  - {railtracks_dir}")
        print(f"  - {railtracks_cli_dir}")
        print("\nTo actually publish, run with --publish flag")
        return

    # Update versions in __init__.py files
    print("\nUpdating version numbers...")
    update_version_in_file(
        railtracks_dir / "src" / "railtracks" / "__init__.py", version
    )
    update_version_in_file(
        railtracks_cli_dir / "src" / "railtracks_cli" / "__init__.py", version
    )

    # Publish packages in order (railtracks first, then railtracks-cli)
    print("\nPublishing packages...")

    # Publish railtracks core package
    core_publish_success = publish_package(railtracks_dir, "railtracks", azure_pat)

    if not core_publish_success:
        print(
            "Failed to publish railtracks core package. Aborting CLI package publish."
        )
        sys.exit(1)

    # Publish railtracks-cli package
    cli_publish_success = publish_package(
        railtracks_cli_dir, "railtracks-cli", azure_pat
    )

    if not cli_publish_success:
        print("Failed to publish railtracks-cli package.")
        sys.exit(1)

    print(f"\n{'=' * 50}")
    print("SUCCESS: Both packages published successfully!")
    print(f"Version: {version}")
    print(f"{'=' * 50}")


if __name__ == "__main__":
    main()
