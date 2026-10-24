import logging
import os
import re
import time
from contextvars import ContextVar
from typing import Callable, Dict, Literal

from rich.console import Console
from rich.text import Text

AllowableLogLevels = Literal[
    "DEBUG",
    "INFO",
    "WARNING",
    "ERROR",
    "CRITICAL",
    "NONE",
]

LoggerNameDisplay = Literal["full", "short"]

str_to_log_level: Dict[str, int] = {
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARNING": logging.WARNING,
    "ERROR": logging.ERROR,
    "CRITICAL": logging.CRITICAL,
    "NONE": logging.CRITICAL + 1,  # no logs emitted
}

# the temporary name for the logger that RT will use.
rt_logger_name = "RT"
rt_logger = logging.getLogger(rt_logger_name)

# node creation, completion, and failure records; the run view prints these for the runs
# it shows
lifecycle_logger_name = f"{rt_logger_name}.lifecycle"

_file_format_string = (
    "%(asctime)s - %(relativeCreated)dms - %(levelname)s - %(name)s - %(message)s"
)


def _make_console() -> Console:
    """Terminal output goes to stderr. In a notebook, rich would send every line as
    its own HTML output, so it writes ANSI text to stdout instead; Jupyter merges
    that into one block (stderr would be tinted like an error)."""
    terminal = Console(stderr=True)
    if terminal.is_jupyter:
        return Console(force_jupyter=False, force_terminal=True)
    return terminal


# Shared by the console handler and the run view so their lines interleave on one clock
_console = _make_console()
_start_time = time.time()

# log levels are ints hence the type hints
_module_logging_level: ContextVar[int | None] = ContextVar(
    "module_logging_level", default=None
)

_module_logging_file: ContextVar[str | os.PathLike | None] = ContextVar(
    "module_logging_file", default=None
)


def _elapsed_text(timestamp: float) -> Text:
    """The ``[+seconds]`` prefix that starts every console line.

    Args:
        timestamp: A ``time.time()``-style timestamp.

    Returns:
        The prefix, styled, measured from when railtracks was imported.
    """
    return Text().append(f"[+{timestamp - _start_time:7.3f}s] ", "bright_black")


def _run_view_level() -> int | None:
    """The level the run view prints at for a run starting in the current context.

    Returns:
        The thread's own level if one was set, else the level railtracks' console was
        enabled with, or None when railtracks' console handler is not attached.
    """
    console_handler = next(
        (h for h in rt_logger.handlers if isinstance(h, _RichConsoleHandler)), None
    )
    if console_handler is None:
        return None
    thread_level = _module_logging_level.get()
    return thread_level if thread_level is not None else console_handler.enabled_level


def _short_suffix_label(segment: str) -> str:
    """
    Last path segment for console short mode: drop leading non-letters (e.g. `_`),
    then capitalize so the label starts with an uppercase letter.
    """
    cleaned = re.sub(r"^[^a-zA-Z]+", "", segment)
    if not cleaned:
        return segment
    return cleaned.capitalize()


def _console_display_name(
    logger_name: str, *, name_style: LoggerNameDisplay, rt_prefix: str
) -> str:
    if name_style == "full":
        return logger_name
    if logger_name == rt_prefix:
        return rt_prefix
    prefix_dot = f"{rt_prefix}."
    if logger_name.startswith(prefix_dot):
        suffix = logger_name.split(".")[-1]
        return f"{rt_prefix}.{_short_suffix_label(suffix)}"
    return logger_name


class ThreadAwareFilter(logging.Filter):
    """
    A filter that uses per-thread logging levels using ContextVar.

    When a log record is processed, this filter executes in the thread that
    created the record, so it correctly retrieves that thread's logging level.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        """
        Determine if the record should be logged based on thread's level.

        Args:
            record: The log record to filter

        Returns:
            True if the record should be logged, False otherwise

        Raises:
            ValueError: If the logging level in ContextVar is invalid
        """
        thread_log_level = _module_logging_level.get()

        return (
            record.levelno >= thread_log_level if thread_log_level is not None else True
        )


class _LifecycleFilter(logging.Filter):
    """Drops lifecycle records for runs the run view is printing, so the console shows
    each node once. A run it isn't printing keeps them, so its failures still show."""

    def __init__(self, run_view_shows: Callable[[str | None], bool]) -> None:
        super().__init__()
        self._run_view_shows = run_view_shows

    def filter(self, record: logging.LogRecord) -> bool:
        if record.name != lifecycle_logger_name:
            return True
        return not self._run_view_shows(getattr(record, "session_id", None))


class _RichConsoleHandler(logging.Handler):
    """Writes RT log records to the shared rich console, coloured by level.

    INFO records print as dim notes in the run view's style; other levels keep the
    logger name and level label. The record is formatted with a plain
    ``logging.Formatter``, so nothing beyond the standard attributes is written onto it
    for handlers further up the tree to pick up.
    """

    _LEVEL_STYLES = {
        logging.DEBUG: "cyan",
        logging.WARNING: "yellow",
        logging.ERROR: "bright_red",
        logging.CRITICAL: "bold red",
    }

    def __init__(
        self,
        *,
        name_style: LoggerNameDisplay = "short",
        enabled_level: int = logging.INFO,
    ) -> None:
        super().__init__()
        self.name_style: LoggerNameDisplay = name_style
        # what the run view prints for runs in threads that set no level of their own
        self.enabled_level = enabled_level

    def emit(self, record: logging.LogRecord) -> None:
        try:
            line = _elapsed_text(record.created)
            if record.levelno == logging.INFO:
                line.append(f"· {self.format(record)}", style="dim")
            else:
                display_name = _console_display_name(
                    record.name, name_style=self.name_style, rt_prefix=rt_logger_name
                )
                line.append(
                    f"{display_name:<12}: {record.levelname:<8} - {self.format(record)}",
                    style=self._LEVEL_STYLES.get(record.levelno, "default"),
                )
            _console.print(line, soft_wrap=True)
        except Exception:
            self.handleError(record)


def _console_handler(
    name_style: LoggerNameDisplay,
    enabled_level: int,
    run_view_shows: Callable[[str | None], bool],
) -> _RichConsoleHandler:
    handler = _RichConsoleHandler(name_style=name_style, enabled_level=enabled_level)
    handler.addFilter(_LifecycleFilter(run_view_shows))
    return handler


# TODO Complete the file integration.
def setup_file_handler(
    *, file_name: str | os.PathLike, file_logging_level: int = logging.INFO
) -> None:
    """
    Setup a logger file handler that writes logs to a file.

    Args:
        file_name: Path to the file where logs will be written.
        file_logging_level: The logging level for the file handler.
            Accepts standard logging levels (DEBUG, INFO, WARNING, ERROR, CRITICAL).
            Defaults to logging.INFO.
    """
    # Unpaired surrogates cannot be encoded; keep them as \u escapes
    file_handler = logging.FileHandler(
        file_name, encoding="utf-8", errors="backslashreplace"
    )
    file_handler.setLevel(file_logging_level)
    file_handler.addFilter(ThreadAwareFilter())

    # date format include milliseconds for better resolution

    default_formatter = logging.Formatter(
        fmt=_file_format_string,
    )

    file_handler.setFormatter(default_formatter)

    # we want to add this file handler to the root logger is it is propagated
    logger = logging.getLogger(rt_logger_name)
    logger.addHandler(file_handler)


def detach_logging_handlers():
    """
    Shuts down the logging system and detaches all logging handlers.
    """
    # Get the root logger
    rt_logger.handlers.clear()
