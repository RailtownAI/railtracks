"""CLI terminal I/O helpers (stdlib + colorama only)."""

from pathlib import Path

from colorama import Fore, Style

from .constants import cli_name


def print_status(message: str) -> None:
    print(f"[{cli_name}] {message}")


def print_success(message: str) -> None:
    print(f"[{cli_name}] {message}")


def print_warning(message: str) -> None:
    print(f"[{cli_name}] {message}")


def print_error(message: str) -> None:
    print(f"[{cli_name}] {message}")


def _print_update_available() -> None:
    print(
        f"{Fore.YELLOW}[{cli_name}] A newer UI is available! "
        f"Run 'railtracks update' to upgrade.{Style.RESET_ALL}"
    )


def confirm_overwrite(path: Path) -> bool:
    """Prompt the user before overwriting `path`. Returns True to proceed."""
    try:
        answer = (
            input(f"[{cli_name}] '{path}' already exists. Overwrite? [y/N] ")
            .strip()
            .lower()
        )
    except (EOFError, KeyboardInterrupt):
        print()
        return False
    return answer in ("y", "yes")
