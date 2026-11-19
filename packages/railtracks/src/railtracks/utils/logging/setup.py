"""Turns railtracks' logging on: the console, an optional log file, and the run view."""

import logging
import os

from railtracks.observability.configure import add_inline_listener

from .config import (
    AllowableLogLevels,
    LoggerNameDisplay,
    ThreadAwareFilter,
    _console_handler,
    _module_logging_file,
    _module_logging_level,
    rt_logger_name,
    setup_file_handler,
    str_to_log_level,
)
from .run_view import RunView

# one view for the whole process; it keeps each session's state apart
_run_view = RunView()


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

    console_handler = _console_handler(name_style, env_level_int, _run_view.is_showing)
    console_handler.addFilter(ThreadAwareFilter())
    logger.addHandler(console_handler)
    add_inline_listener(_run_view.record)

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
    each node and LLM call, ``DEBUG`` adds arguments, responses, the run's result,
    middleware decisions, and context operations. Only ``DEBUG`` prints arguments,
    responses, and results; failure lines include the exception's message at every
    level that shows failures. Each run uses the level of the thread it started in.

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
