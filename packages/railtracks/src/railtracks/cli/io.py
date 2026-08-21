"""CLI stdout helpers (stdlib + colorama only)."""

import os
import sys

from colorama import Fore, Style

from .constants import cli_name


def print_status(message: str) -> None:
    print(f"[{cli_name}] {message}")


def print_success(message: str) -> None:
    print(f"[{cli_name}] {message}")


def _colorize(message: str, color: str) -> str:
    if os.environ.get("NO_COLOR") is not None or not sys.stdout.isatty():
        return message
    return f"{color}{message}{Style.RESET_ALL}"


def print_warning(message: str) -> None:
    print(_colorize(f"[{cli_name}] {message}", Fore.YELLOW))


def print_error(message: str) -> None:
    print(_colorize(f"[{cli_name}] {message}", Fore.RED))


def _print_update_available() -> None:
    print(
        f"{Fore.YELLOW}[{cli_name}] A newer UI is available! "
        f"Run 'railtracks update' to upgrade.{Style.RESET_ALL}"
    )
