#!/usr/bin/env python3

"""
railtracks - A Python development server with JSON API
Usage: railtracks [command]

Commands:
  init    Initialize railtracks environment (setup directories, download UI)
  viz     Start the railtracks development server

- Checks to see if there is a .railtracks directory
- If not, it creates one (and adds it to .gitignore)
- If there is a build directory, it runs the build command
- If there is a .railtracks directory, it starts the server

For testing purposes, you can add `alias railtracks="python railtracks.py"` to your .bashrc or .zshrc
"""

from __future__ import annotations

import importlib.util
import os
import socket
import sys
import tempfile
import threading
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

from colorama import Fore, Style

from railtracks.paths import resolve_railtracks_home

from ._skillkit import (
    CLAUDE,
    CODEX,
    COPILOT,
    CURSOR,
    Skill,
    discover_skills,
    install_skill_directory,
)
from .constants import (
    DEFAULT_PORT,
    cli_directory,
    cli_name,
    latest_ui_url,
)
from .io import (
    _print_update_available,
    print_error,
    print_status,
    print_success,
    print_warning,
)

# ---------------------------------------------------------------------------
# Skill registry — derived from the bundled skill directories on disk
# ---------------------------------------------------------------------------

# The rich objects; the source of truth for everything about a bundled skill.
SKILL_REGISTRY: dict[str, Skill] = discover_skills()

# Legacy skills dict, used for CLI help output and to generate the per-tool SKILL.md files.
SKILLS: dict[str, dict] = {
    name: skill.as_meta() for name, skill in SKILL_REGISTRY.items()
}

SUPPORTED_TOOLS = ("claude", "codex", "copilot", "cursor")


def __getattr__(name: str):
    """Lazy exports for tests (app / RailtracksServer require railtracks[visual])."""
    if name == "app":
        from . import viz_server

        return viz_server.app
    if name == "RailtracksServer":
        from .viz_server import RailtracksServer

        return RailtracksServer
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def get_script_directory():
    """Get the directory where this script is located"""
    return Path(__file__).parent.absolute()


def _visual_dependencies_available() -> bool:
    return (
        importlib.util.find_spec("fastapi") is not None
        and importlib.util.find_spec("uvicorn") is not None
    )


def _warn_if_visual_deps_missing() -> None:
    if _visual_dependencies_available():
        return
    print_warning(
        "The visualizer (railtracks viz) requires extra dependencies. "
        "Install with: pip install 'railtracks[visual]'."
    )


def is_port_in_use(port):
    """Check if a port is already in use"""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        try:
            sock.bind(("localhost", port))
            return False  # Port is available
        except OSError:
            return True  # Port is in use


def create_railtracks_dir():
    """Create .railtracks directory if it doesn't exist and add to .gitignore"""
    railtracks_dir = resolve_railtracks_home()
    if not railtracks_dir.exists():
        print_status(f"Creating {cli_directory} directory...")
        railtracks_dir.mkdir(parents=True, exist_ok=True)
        print_success(f"Created {railtracks_dir}")

        gitignore_path = railtracks_dir.parent / ".gitignore"
        if gitignore_path.exists():
            with open(gitignore_path) as f:
                gitignore_content = f.read()

            if cli_directory not in gitignore_content:
                print_status(f"Adding {cli_directory} to .gitignore...")
                with open(gitignore_path, "a") as f:
                    f.write(f"\n{cli_directory}\n")
                print_success(f"Added {cli_directory} to .gitignore")
        else:
            print_status("Creating .gitignore file...")
            with open(gitignore_path, "w") as f:
                f.write(f"{cli_directory}\n")
            print_success(f"Created .gitignore with {cli_directory}")
    else:
        print_status(f"Using existing {railtracks_dir}")


def get_stored_ui_version():
    """Get the stored UI version (ETag) from disk"""
    version_file = resolve_railtracks_home() / ".ui_version"
    try:
        if version_file.exists():
            return version_file.read_text().strip()
    except Exception:
        pass
    return None


def save_ui_version(version: str):
    """Save the UI version (ETag) to disk"""
    version_file = resolve_railtracks_home() / ".ui_version"
    try:
        version_file.write_text(version)
    except Exception:
        pass


def get_remote_ui_version():
    """Get the remote UI version (ETag or Last-Modified) via HEAD request"""
    try:
        req = urllib.request.Request(latest_ui_url, method="HEAD")
        with urllib.request.urlopen(req, timeout=5) as response:
            return response.headers.get("ETag") or response.headers.get("Last-Modified")
    except Exception:
        return None


def check_for_ui_update():
    """Check if there's an updated UI available and notify the user"""
    stored = get_stored_ui_version()
    if stored is None:
        return
    remote = get_remote_ui_version()
    if remote is not None and remote != stored:
        _print_update_available()


def download_and_extract_ui():
    """Download the latest frontend UI and extract it to .railtracks/ui"""
    ui_url = latest_ui_url
    ui_dir = resolve_railtracks_home() / "ui"

    print_status("Downloading latest frontend UI...")

    temp_zip_path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".zip") as temp_file:
            temp_zip_path = temp_file.name

        print_status(f"Downloading from: {ui_url}")
        ui_version = None
        with urllib.request.urlopen(ui_url) as response:
            ui_version = response.headers.get("ETag") or response.headers.get(
                "Last-Modified"
            )
            with open(temp_zip_path, "wb") as f:
                f.write(response.read())

        ui_dir.mkdir(parents=True, exist_ok=True)

        print_status("Extracting UI files...")
        with zipfile.ZipFile(temp_zip_path, "r") as zip_ref:
            zip_ref.extractall(ui_dir)

        if ui_version:
            save_ui_version(ui_version)

        print_success("Frontend UI downloaded and extracted successfully")
        print_status(f"UI files available in: {ui_dir}")
        _warn_if_visual_deps_missing()

    except urllib.error.URLError as e:
        print_error(f"Failed to download UI: {e}")
        print_error("Please check your internet connection and try again")
        sys.exit(1)
    except zipfile.BadZipFile as e:
        print_error(f"Failed to extract UI zip file: {e}")
        print_error("The downloaded file may be corrupted")
        sys.exit(1)
    except Exception as e:
        print_error(f"Unexpected error during UI download/extraction: {e}")
        sys.exit(1)
    finally:
        if temp_zip_path and os.path.exists(temp_zip_path):
            os.unlink(temp_zip_path)


def init_railtracks():
    """Initialize the railtracks environment"""
    print_status("Initializing railtracks environment...")

    create_railtracks_dir()

    download_and_extract_ui()

    print_success("railtracks initialization completed!")
    print_status("You can now run 'railtracks viz' to start the server")


def update_railtracks():
    """Update the frontend UI to the latest version"""
    print_status("Updating the frontend UI to the latest version...")
    download_and_extract_ui()
    print_success("Frontend UI updated successfully!")


# ---------------------------------------------------------------------------
# `railtracks add` command
# ---------------------------------------------------------------------------


def _add_claude(skill: Skill, force: bool) -> list[Path]:
    """Install a skill for Claude Code as a skill directory, and report what it wrote.

    Thin by design: everything here that another assistant would also need lives in
    `_skillkit.install`, parameterised by root path and projection, so the remaining
    handlers become the same two values rather than the same function again.
    """
    return install_skill_directory(skill, CLAUDE, force)


def _add_codex(skill: Skill, force: bool) -> list[Path]:
    """Install a skill for Codex as a skill directory under .agents/skills."""
    return install_skill_directory(skill, CODEX, force)


def _add_copilot(skill: Skill, force: bool) -> list[Path]:
    """Install a skill for GitHub Copilot as a skill directory under .github/skills."""
    return install_skill_directory(skill, COPILOT, force)


def _add_cursor(skill: Skill, force: bool) -> list[Path]:
    """Install a skill for Cursor as a skill directory under .cursor/skills."""
    return install_skill_directory(skill, CURSOR, force)


_TOOL_HANDLERS = {
    "claude": _add_claude,
    "codex": _add_codex,
    "copilot": _add_copilot,
    "cursor": _add_cursor,
}


def add_skill(spec: str, force: bool = False) -> list[Path] | None:
    """Parse <tool>:<skill-name> and install the skill for the given AI coding tool.

    Returns the files the handler wrote, for handlers that report them.
    """
    if ":" not in spec:
        print_error(
            f"Invalid format '{spec}'. Expected '<tool>:<skill>', e.g. 'claude:agent-builder'."
        )
        print_status(f"Supported tools: {', '.join(SUPPORTED_TOOLS)}")
        print_status(f"Available skills: {', '.join(SKILLS)}")
        sys.exit(1)

    tool, skill_name = spec.split(":", 1)
    tool = tool.lower()

    if tool not in _TOOL_HANDLERS:
        print_error(
            f"Unknown tool '{tool}'. Supported tools: {', '.join(SUPPORTED_TOOLS)}"
        )
        sys.exit(1)

    if skill_name not in SKILLS:
        print_error(
            f"Unknown skill '{skill_name}'. Available skills: {', '.join(SKILLS)}"
        )
        sys.exit(1)

    return _TOOL_HANDLERS[tool](SKILL_REGISTRY[skill_name], force)


def list_skills() -> None:
    """Print the bundled skills and the assistants they can be installed for."""
    rst = Style.RESET_ALL
    bold = Style.BRIGHT
    dim = Style.DIM
    cyan = Fore.CYAN
    green = Fore.GREEN

    print()
    print(f"  {bold}Available skills:{rst}")
    print()
    for skill_name, meta in SKILLS.items():
        print(f"  {cyan}{bold}{skill_name}{rst}  {dim}{meta['argument_hint']}{rst}")
        print(f"    {meta['description']}")
        print()
    print(f"  {bold}Supported tools:{rst}  {', '.join(SUPPORTED_TOOLS)}")
    print()
    print(f"  {dim}Install with:{rst}  {green}{cli_name} add <tool>:<skill>{rst}")
    print()


def _print_help():
    """Print styled help output."""
    rst = Style.RESET_ALL
    bold = Style.BRIGHT
    dim = Style.DIM
    cyan = Fore.CYAN
    green = Fore.GREEN
    yellow = Fore.YELLOW

    def cmd(name, description):
        return f"  {cyan}{bold}{name:<10}{rst}  {description}"

    def example(invocation, comment):
        return f"  {green}{invocation}{rst}  {dim}# {comment}{rst}"

    print()
    print(f"  {cyan}{bold}{cli_name}{rst}  {dim}— AI agent framework{rst}")
    print()
    print(f"  {bold}Usage:{rst}  {cli_name} {yellow}<command>{rst}")
    print()
    print(f"  {bold}Commands:{rst}")
    print(
        cmd(
            "init",
            f"Initialize {cli_name} environment (setup directories, download portable UI)",
        )
    )
    print(cmd("update", "Update the frontend UI to the latest version"))
    print(cmd("viz", f"Start the {cli_name} development server"))
    print(
        cmd(
            "add",
            f"Install an AI coding assistant skill  {dim}(--list to see them all){rst}",
        )
    )
    print()
    print(f"  {bold}Examples:{rst}")
    print(example(f"{cli_name} init", "Initialize visualizer environment"))
    print(example(f"{cli_name} viz", "Start visualizer web app"))
    print(
        example(
            f"{cli_name} add claude:agent-builder",
            "Install agent-builder skill for Claude Code",
        )
    )
    print(
        example(
            f"{cli_name} add codex:agent-builder",
            "Install agent-builder skill for Codex",
        )
    )
    print(
        example(
            f"{cli_name} add copilot:agent-builder",
            "Install agent-builder skill for GitHub Copilot",
        )
    )
    print(
        example(
            f"{cli_name} add cursor:agent-builder",
            "Install agent-builder skill for Cursor",
        )
    )
    print(
        example(
            f"{cli_name} add --list",
            "List every bundled skill and supported tool",
        )
    )
    print()


def _exit_visual_deps_missing() -> None:
    print_error("The visualizer requires optional dependencies.")
    print_status("Install with: pip install 'railtracks[visual]'")
    sys.exit(1)


def _run_add(args: list[str]) -> None:
    """Handle `railtracks add`: either list the bundled skills or install one."""
    if any(a in ("--list", "-l") for a in args):
        list_skills()
        return

    if not args or args[0].startswith("-"):
        print_error(
            "Usage: railtracks add [--force] <tool>:<skill> | railtracks add --list"
        )
        print_status(f"Supported tools: {', '.join(SUPPORTED_TOOLS)}")
        print_status(f"Available skills: {', '.join(SKILLS)}")
        sys.exit(1)

    force = "--force" in args
    spec = next((a for a in args if not a.startswith("-")), None)
    add_skill(spec, force=force)


def main():
    """Main function"""
    if len(sys.argv) < 2:
        _print_help()
        sys.exit(1)

    command = sys.argv[1]

    if command == "init":
        init_railtracks()
    elif command == "update":
        update_railtracks()
    elif command == "viz":
        if not _visual_dependencies_available():
            _exit_visual_deps_missing()

        if is_port_in_use(DEFAULT_PORT):
            print_error(f"Port {DEFAULT_PORT} is already in use!")
            print_status("Please stop the existing server.")
            sys.exit(1)

        from .viz_server import RailtracksServer

        create_railtracks_dir()

        ui_index = resolve_railtracks_home() / "ui" / "index.html"
        if not ui_index.exists():
            print_status("UI not found — downloading...")
            download_and_extract_ui()

        update_thread = threading.Thread(target=check_for_ui_update, daemon=True)
        update_thread.start()

        server = RailtracksServer()
        server.start()
    elif command == "add":
        _run_add(sys.argv[2:])
    else:
        print(f"{Fore.RED}Unknown command: {command}{Style.RESET_ALL}")
        print(f"{Style.DIM}Available commands: init, update, viz, add{Style.RESET_ALL}")
        sys.exit(1)


if __name__ == "__main__":
    main()
