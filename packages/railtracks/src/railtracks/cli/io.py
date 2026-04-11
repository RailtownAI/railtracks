"""CLI stdout helpers (stdlib + colorama only)."""

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
