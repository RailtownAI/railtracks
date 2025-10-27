import logging
import os
import re
from contextvars import ContextVar
from typing import Dict, Literal

from colorama import Fore, init

AllowableLogLevels = Literal[
    "DEBUG",
    "INFO",
    "WARNING",
    "ERROR",
    "CRITICAL",
    "NONE",
]

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
rt_logger.setLevel(logging.DEBUG)

_default_format_string = "%(timestamp_color)s[+%(relative_seconds)-7ss] %(level_color)s%(name)-12s: %(levelname)-8s - %(message)s%(default_color)s"


_file_format_string = (
    "%(asctime)s - %(relative_seconds)s - %(levelname)ss - %(name)s - %(message)s"
)
# _file_format_string = "[%(asctime)] %(timestamp_color)s[+%(relative_seconds)-7ss] %(level_color)s%(name)-12s: %(levelname)-8s - %(message)s%(default_color)s"

# log levels are ints hence the type hints
_pre_session_log_level: ContextVar[int | None] = ContextVar(
    "pre_session_log_level", default=None
)
_pre_session_log_file: ContextVar[str | os.PathLike | None] = ContextVar(
    "pre_session_log_file", default=None
)

_module_logging_level: ContextVar[int | None] = ContextVar(
    "module_logging_level", default=None
)

_module_logging_file: ContextVar[str | os.PathLike | None] = ContextVar(
    "module_logging_file", default=None
)

_session_has_override: ContextVar[bool] = ContextVar(
    "session_has_override", default=False
)

# Initialize colorama
init(autoreset=True)


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


class ColorfulFormatter(logging.Formatter):
    """
    A simple formatter that can be used to format log messages with colours based on the log level and specific keywords.
    """

    def __init__(self, fmt=None, datefmt=None):
        super().__init__(fmt, datefmt)
        self.level_colors = {
            logging.DEBUG: Fore.CYAN,
            logging.INFO: Fore.WHITE,  # White for logger.info
            logging.WARNING: Fore.YELLOW,
            logging.ERROR: Fore.LIGHTRED_EX,  # Red for logger.exception or logger.error
            logging.CRITICAL: Fore.RED,
        }
        self.keyword_colors = {
            "FAILED": Fore.RED,
            "WARNING": Fore.YELLOW,
            "CREATED": Fore.GREEN,
            "DONE": Fore.BLUE,
        }
        self.timestamp_color = Fore.LIGHTBLACK_EX
        self.default_color = Fore.WHITE

        # precompute the regex patterns
        self.keyword_patterns = {
            keyword: re.compile(rf"(?i)\b({keyword})\b")
            for keyword in self.keyword_colors.keys()
        }

    def format(self, record: logging.LogRecord) -> str:
        """
        Format the log record with colors for console output.

        Creates a temporary copy of attributes to avoid mutating the original record.
        """
        level_color = self.level_colors.get(record.levelno, self.default_color)

        # Get the formatted message (doesn't modify record)
        message = record.getMessage()

        colored_message = message
        for keyword, color in self.keyword_colors.items():
            colored_message = self.keyword_patterns[keyword].sub(
                f"{color}\\1{level_color}",
                colored_message,
            )

        record.timestamp_color = self.timestamp_color
        record.level_color = level_color
        record.default_color = self.default_color
        record.relative_seconds = f"{record.relativeCreated / 1000:.3f}"

        original_msg = record.msg
        original_args = record.args

        record.msg = colored_message
        record.args = ()

        try:
            result = super().format(record)
        finally:
            # ALWAYS restore, even if formatting fails
            record.msg = original_msg
            record.args = original_args

        return result


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
):
    """
    Prepares the logger based on the setting and optionally sets up the file handler if a path is provided.
    """
    detach_logging_handlers()
    if path is not None:
        setup_file_handler(file_name=path, file_logging_level=logging.INFO)

    console_handler = logging.StreamHandler()
    formatter = ColorfulFormatter(fmt=_default_format_string)
    console_handler.setFormatter(formatter)

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


def detach_logging_handlers():
    """
    Shuts down the logging system and detaches all logging handlers.
    """
    # Get the root logger
    rt_logger.handlers.clear()


def initialize_module_logging() -> None:
    """
    Initialize module-level logging when railtracks is first imported.

    Reads configuration from environment variables if set:
    - RT_LOG_LEVEL: Sets the logging level
    - RT_LOG_FILE: Optional path to a log file

    If not set, defaults to INFO level with no log file.

    This sets up shared handlers once with a ThreadAwareFilter that checks
    each thread's ContextVar to determine what should be logged.

    """

    env_level = os.getenv("RT_LOG_LEVEL", "INFO").upper()
    env_log_file = os.getenv("RT_LOG_FILE", None)

    env_level = str_to_log_level.get(env_level, None)  # if "" -> None

    _module_logging_level.set(env_level)
    _module_logging_file.set(env_log_file)

    logger = logging.getLogger(rt_logger_name)

    if logger.handlers:
        return

    console_handler = logging.StreamHandler()
    console_handler.addFilter(ThreadAwareFilter())
    formatter = ColorfulFormatter(fmt=_default_format_string)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # Set up file handler if specified
    if env_log_file is not None:
        setup_file_handler(file_name=env_log_file, file_logging_level=logging.INFO)


def configure_module_logging(
    level: AllowableLogLevels | None = None, log_file: str | os.PathLike | None = None
) -> None:
    """
    Configure module-level logging at runtime for the current thread.

    This updates the logging configuration for the current thread.
    Changes apply immediately and persist for the lifetime of the thread.

    If a Session is currently active with custom logging settings, this will
    raise an error to prevent conflicts.

    Args:
        level: The logging level to use
        log_file: Optional path to a log file. If None, logs only to console.
    """
    if _session_has_override.get():
        raise RuntimeError(
            "Cannot configure module-level logging while a session has overridden logging settings."
        )

    if level is not None:
        _module_logging_level.set(str_to_log_level[level])
    if log_file is not None:
        _module_logging_file.set(log_file)


def mark_session_logging_override(
    session_level: AllowableLogLevels, session_log_file: str | os.PathLike | None
) -> None:
    """
    Mark that a session has overridden module-level logging for this thread.

    Stores the current thread's logging config for later restoration and updates
    the thread's ContextVar to the session-specific logging level.

    With ThreadAwareFilter, we don't need to reconfigure handlers - just updating
    the ContextVar is sufficient since the filter checks it for each log record.

    Args:
        session_level: The session's logging level
        session_log_file: The session's log file (or None)
    """
    # Save the current thread's config
    _pre_session_log_level.set(_module_logging_level.get())
    _pre_session_log_file.set(_module_logging_file.get())

    _session_has_override.set(True)

    _module_logging_level.set(str_to_log_level[session_level])

    # TODO: Handle session_log_file if needed (file handler per thread)
    if session_log_file is not None:
        _module_logging_file.set(session_log_file)


def restore_module_logging() -> None:
    """
    Restore module-level logging after a session with custom logging ends.

    This restores the thread's ContextVar to the pre-session value.
    Since handlers are shared and use ThreadAwareFilter, we don't need to detach/reattach handlers.
    """
    if not _session_has_override.get():
        return

    # restore
    restored_level = _pre_session_log_level.get()
    restored_file = _pre_session_log_file.get()

    if restored_level is not None:
        _module_logging_level.set(restored_level)
    else:
        # Fallback to INFO if no pre-session level was stored
        _module_logging_level.set(str_to_log_level["INFO"])

    if restored_file is not None:
        _module_logging_file.set(restored_file)
    else:
        _module_logging_file.set(None)

    _session_has_override.set(False)
    _pre_session_log_level.set(None)
    _pre_session_log_file.set(None)
