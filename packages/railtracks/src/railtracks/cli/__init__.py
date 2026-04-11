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
import json
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

from .constants import (
    DEFAULT_PORT,
    UI_VERSION_FILE,
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
# Skill registry — maps skill names to their metadata
# ---------------------------------------------------------------------------

SKILLS = {
    "agent-builder": {
        "name": "agent-builder",
        "description": (
            "Build an agent using the railtracks Python framework. "
            "Use when the user wants to create an AI agent, tool-calling workflow, "
            "or multi-agent system with railtracks."
        ),
        "argument_hint": "[describe what the agent should do]",
    },
}

SUPPORTED_TOOLS = ("claude", "copilot", "cursor")


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
        "Install with: pip install 'railtracks[visual]' "
        "(or pip install 'railtracks[cli]' for backward compatibility)."
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
    railtracks_dir = Path(cli_directory)
    if not railtracks_dir.exists():
        print_status(f"Creating {cli_directory} directory...")
        railtracks_dir.mkdir(exist_ok=True)
        print_success(f"Created {cli_directory} directory")

    gitignore_path = Path(".gitignore")
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


def get_stored_ui_version():
    """Get the stored UI version (ETag) from disk"""
    version_file = Path(UI_VERSION_FILE)
    try:
        if version_file.exists():
            return version_file.read_text().strip()
    except Exception:
        pass
    return None


def save_ui_version(version: str):
    """Save the UI version (ETag) to disk"""
    version_file = Path(UI_VERSION_FILE)
    try:
        version_file.write_text(version)
    except Exception:
        pass


def get_remote_ui_version():
    """Get the remote UI version (ETag or Last-Modified) via HEAD request"""
    try:
        req = urllib.request.Request(latest_ui_url, method="HEAD")
        with urllib.request.urlopen(req, timeout=5) as response:
            return response.headers.get("ETag") or response.headers.get(
                "Last-Modified"
            )
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
    ui_dir = Path(f"{cli_directory}/ui")

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


def _load_skill_content(skill_name: str) -> str:
    """Load bundled skill content from the skills directory."""
    skills_dir = Path(__file__).parent / "skills"
    skill_file = skills_dir / f"{skill_name}.md"
    if not skill_file.exists():
        print_error(f"Skill '{skill_name}' not found in bundled skills.")
        sys.exit(1)
    return skill_file.read_text(encoding="utf-8")


def _confirm_overwrite(file_path: Path) -> bool:
    """Prompt the user to confirm overwriting an existing file. Returns True to proceed."""
    try:
        answer = (
            input(f"[{cli_name}] '{file_path}' already exists. Overwrite? [y/N] ")
            .strip()
            .lower()
        )
    except (EOFError, KeyboardInterrupt):
        print()
        return False
    return answer in ("y", "yes")


def _add_claude(skill_name: str, meta: dict, content: str, force: bool) -> None:
    """Install skill for Claude Code as a SKILL.md file."""
    target = Path(".claude") / "skills" / skill_name / "SKILL.md"
    if target.exists() and not force:
        if not _confirm_overwrite(target):
            print_status("Aborted.")
            sys.exit(0)

    target.parent.mkdir(parents=True, exist_ok=True)
    frontmatter = (
        "---\n"
        f"name: {meta['name']}\n"
        f"description: {meta['description']}\n"
        f'argument-hint: "{meta["argument_hint"]}"\n'
        "---\n\n"
    )
    target.write_text(frontmatter + content, encoding="utf-8")
    print_success(f"Installed '{skill_name}' for Claude Code → {target}")


def _add_copilot(skill_name: str, meta: dict, content: str, force: bool) -> None:  # noqa: ARG001
    """Install skill for GitHub Copilot by appending to copilot-instructions.md."""
    target = Path(".github") / "copilot-instructions.md"
    start_marker = f"<!-- railtracks:{skill_name}:start -->"
    end_marker = f"<!-- railtracks:{skill_name}:end -->"

    if target.exists():
        existing = target.read_text(encoding="utf-8")
        if start_marker in existing:
            print_warning(
                f"Skill '{skill_name}' is already present in {target}. "
                "Remove the existing section and re-run to update it, or use --force."
            )
            if not force:
                sys.exit(0)
            start_idx = existing.index(start_marker)
            end_idx = existing.index(end_marker) + len(end_marker)
            existing = existing[:start_idx].rstrip() + existing[end_idx:]
            target.write_text(existing, encoding="utf-8")
    else:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("", encoding="utf-8")

    section = f"\n\n{start_marker}\n{content.strip()}\n{end_marker}\n"
    with open(target, "a", encoding="utf-8") as f:
        f.write(section)
    print_success(f"Installed '{skill_name}' for GitHub Copilot → {target}")


def _add_cursor(skill_name: str, meta: dict, content: str, force: bool) -> None:
    """Install skill for Cursor as a .mdc rules file."""
    target = Path(".cursor") / "rules" / f"{skill_name}.mdc"
    if target.exists() and not force:
        if not _confirm_overwrite(target):
            print_status("Aborted.")
            sys.exit(0)

    target.parent.mkdir(parents=True, exist_ok=True)
    frontmatter = (
        f"---\ndescription: {meta['description']}\nalwaysApply: false\n---\n\n"
    )
    target.write_text(frontmatter + content, encoding="utf-8")
    print_success(f"Installed '{skill_name}' for Cursor → {target}")


_TOOL_HANDLERS = {
    "claude": _add_claude,
    "copilot": _add_copilot,
    "cursor": _add_cursor,
}


def add_skill(spec: str, force: bool = False) -> None:
    """Parse <tool>:<skill-name> and install the skill for the given AI coding tool."""
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

    meta = SKILLS[skill_name]
    content = _load_skill_content(skill_name)
    _TOOL_HANDLERS[tool](skill_name, meta, content, force)


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
            f"Install an AI coding assistant skill  {dim}(e.g. {cli_name} add claude:agent-builder){rst}",
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
    print()


def _exit_visual_deps_missing() -> None:
    print_error("The visualizer requires optional dependencies.")
    print_status("Install with: pip install 'railtracks[visual]'")
    print_status(
        "(or: pip install 'railtracks[cli]' — same dependencies, backward compatible)"
    )
    sys.exit(1)


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

        update_thread = threading.Thread(target=check_for_ui_update, daemon=True)
        update_thread.start()

        server = RailtracksServer()
        server.start()
    elif command == "add":
        args = sys.argv[2:]
        if not args or args[0].startswith("-"):
            print_error("Usage: railtracks add [--force] <tool>:<skill>")
            print_status(f"Supported tools: {', '.join(SUPPORTED_TOOLS)}")
            print_status(f"Available skills: {', '.join(SKILLS)}")
            sys.exit(1)
        force = "--force" in args
        spec = next((a for a in args if not a.startswith("-")), None)
        add_skill(spec, force=force)
    else:
        print(f"{Fore.RED}Unknown command: {command}{Style.RESET_ALL}")
        print(f"{Style.DIM}Available commands: init, update, viz, add{Style.RESET_ALL}")
        sys.exit(1)


if __name__ == "__main__":
    main()
