import logging
import os
import re
import time
from contextvars import ContextVar
from typing import Dict, Literal

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

_file_format_string = (
    "%(asctime)s - %(relativeCreated)d - %(levelname)ss - %(name)s - %(message)s"
)

# Marks a record the run view already shows, so the console handler skips it
LIFECYCLE_EXTRA = {"rt_lifecycle": True}

# Shared by the console handler and the run view so their lines interleave on one clock
console = Console(stderr=True)
_start_time = time.time()

# Default level of the run view; None until railtracks installs its console handler
_console_level: int | None = None

# log levels are ints hence the type hints
_module_logging_level: ContextVar[int | None] = ContextVar(
    "module_logging_level", default=None
)

_module_logging_file: ContextVar[str | os.PathLike | None] = ContextVar(
    "module_logging_file", default=None
)


def elapsed_text(timestamp: float) -> Text:
    """The ``[+seconds]`` prefix that starts every console line.

    Args:
        timestamp: A ``time.time()``-style timestamp.

    Returns:
        The prefix, styled, measured from when railtracks was imported.
    """
    return Text().append(f"[+{timestamp - _start_time:7.3f}s] ", "bright_black")


def run_view_level() -> int | None:
    """The level the run view prints at for a run starting in the current context.

    Returns:
        The thread's own level if one was set, else the level railtracks' console was
        enabled with, or None when railtracks' console is not enabled.
    """
    if _console_level is None:
        return None
    thread_level = _module_logging_level.get()
    return thread_level if thread_level is not None else _console_level


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


class LifecycleFilter(logging.Filter):
    """Drops the node lifecycle records that the run view already prints."""

    def filter(self, record: logging.LogRecord) -> bool:
        return not getattr(record, "rt_lifecycle", False)


class RichConsoleHandler(logging.Handler):
    """Writes RT log records to the shared rich console, coloured by level.

    INFO records print as dim notes in the run view's style; other levels keep the
    logger name and level label. The record is formatted with a plain ``logging.Formatter``, so nothing beyond the
    standard attributes is written onto it for handlers further up the tree to pick up.
    """

    _LEVEL_STYLES = {
        logging.DEBUG: "cyan",
        logging.WARNING: "yellow",
        logging.ERROR: "bright_red",
        logging.CRITICAL: "bold red",
    }

    def __init__(self, *, name_style: LoggerNameDisplay = "short") -> None:
        super().__init__()
        self.name_style: LoggerNameDisplay = name_style

    def emit(self, record: logging.LogRecord) -> None:
        try:
            line = elapsed_text(record.created)
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
            console.print(line, soft_wrap=True)
        except Exception:
            self.handleError(record)


def _console_handler(name_style: LoggerNameDisplay) -> RichConsoleHandler:
    handler = RichConsoleHandler(name_style=name_style)
    handler.addFilter(LifecycleFilter())
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
    file_handler = logging.FileHandler(file_name)
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


def prepare_logger(
    *,
    setting: AllowableLogLevels | None,
    path: str | os.PathLike | None = None,
    name_style: LoggerNameDisplay = "short",
):
    """
    Prepares the logger based on the setting and optionally sets up the file handler if a path is provided.
    """
    global _console_level

    detach_logging_handlers()
    if path is not None:
        setup_file_handler(file_name=path, file_logging_level=logging.INFO)

    console_handler = _console_handler(name_style)

    logger = logging.getLogger(rt_logger_name)

    match setting:
        case "DEBUG":
            console_handler.setLevel(logging.DEBUG)
        case "INFO":
            console_handler.setLevel(logging.INFO)
        case "WARNING":
            console_handler.setLevel(logging.WARNING)
        case "ERROR":
            console_handler.setLevel(logging.ERROR)
        case "CRITICAL":
            console_handler.setLevel(logging.CRITICAL)
        case "NONE":
            console_handler.addFilter(lambda x: False)
        case None:
            pass
        case _:
            raise ValueError("Invalid log level setting")

    logger.addHandler(console_handler)
    _console_level = str_to_log_level[setting or "INFO"]


def detach_logging_handlers():
    """
    Shuts down the logging system and detaches all logging handlers.
    """
    global _console_level

    # Get the root logger
    rt_logger.handlers.clear()
    _console_level = None


def initialize_module_logging(
    level: AllowableLogLevels | None = None,
    log_file: str | os.PathLike | None = None,
    *,
    name_style: LoggerNameDisplay = "short",
) -> None:
    """
    Initialize module-level logging (internal). Use enable_logging() for the public API.

    When level/log_file are None, reads from environment variables:
    - RT_LOG_LEVEL: Sets the logging level
    - RT_LOG_FILE: Optional path to a log file

    If not set, defaults to INFO level with no log file.

    This sets up shared handlers once with a ThreadAwareFilter that checks
    each thread's ContextVar to determine what should be logged. The same level
    decides what the run view prints for runs started in that thread.
    """
    global _console_level

    env_level_str = (
        level if level is not None else os.getenv("RT_LOG_LEVEL", "INFO")
    ).upper()
    env_log_file = (
        log_file if log_file is not None else os.getenv("RT_LOG_FILE") or None
    )

    env_level_int = str_to_log_level.get(env_level_str, str_to_log_level["INFO"])

    _module_logging_level.set(env_level_int)
    _module_logging_file.set(env_log_file)

    logger = logging.getLogger(rt_logger_name)
    logger.setLevel(env_level_str)

    # Only skip if there are real handlers (app or user already configured).
    # NullHandler is added by the library so "No handlers" is never raised.
    non_null_handlers = [
        h for h in logger.handlers if not isinstance(h, logging.NullHandler)
    ]
    if non_null_handlers:
        return

    for h in list(logger.handlers):
        if isinstance(h, logging.NullHandler):
            logger.removeHandler(h)

    console_handler = _console_handler(name_style)
    console_handler.addFilter(ThreadAwareFilter())
    logger.addHandler(console_handler)
    _console_level = env_level_int

    # Set up file handler if specified
    if env_log_file is not None:
        setup_file_handler(file_name=env_log_file, file_logging_level=logging.INFO)


def enable_logging(
    level: AllowableLogLevels = "INFO",
    log_file: str | os.PathLike | None = None,
    *,
    name_style: LoggerNameDisplay = "short",
) -> None:
    """
    Opt-in helper to enable Railtracks logging. Call this explicitly from your
    application entry point (CLI, main.py, server startup); the library never
    calls it automatically.

    Uses the given level and log_file; when None, reads RT_LOG_LEVEL and
    RT_LOG_FILE from the environment. Sets up console output (and optional file)
    with a ThreadAwareFilter for per-thread level control.

    Runs print as an indented run view built from session events. The level picks
    what it shows: ``WARNING`` the run's start and end plus failures, ``INFO`` adds
    each node and LLM call, ``DEBUG`` adds arguments, responses, middleware
    decisions, and context operations. Each run uses the level of the thread it
    started in.

    Args:
        level: Logging level (default "INFO"). Overridden by RT_LOG_LEVEL when None.
        log_file: Optional path for a log file. Overridden by RT_LOG_FILE when None.
        name_style: Console column for logger name: ``full`` (dotted name) or
            ``short`` (``RT.<Label>``: last segment with leading non-letters stripped,
            then capitalized). Default ``short``.
    """
    initialize_module_logging(
        level=level,
        log_file=log_file,
        name_style=name_style,
    )
