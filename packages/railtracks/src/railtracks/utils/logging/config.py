import logging
import os
import re
from typing import Dict, Literal, cast

from colorama import Fore, init

AllowableLogLevels = Literal["VERBOSE", "REGULAR", "QUIET", "NONE"]
allowable_log_levels_set = {"VERBOSE", "REGULAR", "QUIET", "NONE"}

# the temporary name for the logger that RT will use.
rt_logger_name = "RT"
rt_logger = logging.getLogger(rt_logger_name)
rt_logger.setLevel(logging.INFO)

_default_format_string = "%(timestamp_color)s[+%(relative_seconds)-7ss] %(level_color)s%(name)-12s: %(levelname)-8s - %(message)s%(default_color)s"


_file_format_string = "%(asctime)s %(levelname)s - %(message)s"

_module_logging_config: Dict[str, AllowableLogLevels | str | os.PathLike | None] = {
    "level": None,
    "log_file": None,
}
_session_has_override: bool = False
_pre_session_config: Dict[str, AllowableLogLevels | str | os.PathLike | None] = {}

# Initialize colorama
init(autoreset=True)


class ColorfulFormatter(logging.Formatter):
    """
    A simple formatter that can be used to format log messages with colours based on the log level and specific keywords.
    """

    def __init__(self, fmt=None, datefmt=None):
        super().__init__(fmt, datefmt)
        self.level_colors = {
            logging.INFO: Fore.WHITE,  # White for logger.info
            logging.ERROR: Fore.LIGHTRED_EX,  # Red for logger.exception or logger.error
            logging.WARNING: Fore.YELLOW,
            logging.DEBUG: Fore.CYAN,
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

    def format(self, record):
        # Apply color based on log level
        level_color = self.level_colors.get(record.levelno, self.default_color)
        record.msg = record.getMessage()

        # Highlight specific keywords in the log message
        for keyword, color in self.keyword_colors.items():
            record.msg = re.sub(
                rf"(?i)\b({keyword})\b",
                f"{color}\\1{level_color}",
                record.msg,
            )

        # Apply color to the log
        record.timestamp_color = self.timestamp_color
        record.level_color = level_color
        record.default_color = self.default_color

        if not hasattr(record, "session_id"):
            record.session_id = "Unknown"

        if not hasattr(record, "run_id"):
            record.run_id = "Unknown"

        if not hasattr(record, "node_id"):
            record.node_id = "Unknown"

        # record.levelname = f"{level_color}{record.levelname}{self.default_color}"
        record.relative_seconds = f"{record.relativeCreated / 1000:.3f}"
        return super().format(record)


def level_filter(value: int):
    """
    A helper function to create a filter function that filters log records based on their level.
    """

    def filter_func(record: logging.LogRecord):
        return record.levelno >= value

    return filter_func


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
    setting: AllowableLogLevels,
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
    logger.addHandler(console_handler)

    if setting == "VERBOSE":
        logger.setLevel(logging.DEBUG)
    elif setting == "REGULAR":
        logger.setLevel(logging.INFO)
    elif setting == "QUIET":
        logger.setLevel(logging.WARNING)
    elif setting == "NONE":
        logger.addFilter(lambda x: False)
        logger.addHandler(logging.NullHandler())
    else:
        raise ValueError("Invalid log level setting")


def detach_logging_handlers():
    """
    Shuts down the logging system and detaches all logging handlers.
    """
    # Get the root logger
    rt_logger.handlers.clear()


def initialize_module_logging() -> None:
    """
    Initliaze module-level logging when railtracks is first imported.

    Reads configuration from environment variables if set:
    - RT_LOG_LEVEL: Sets the logging level (VERBOSE, REGULAR, QUIET, NONE)
    - RT_LOG_FILE: Optional path to a log file

    If not set, defaults to REGULAR level with no log file.
    """

    global _module_logging_config

    env_level = os.getenv("RT_LOG_LEVEL", "REGULAR").upper()
    env_log_file = os.getenv("RT_LOG_FILE", None)

    if env_level not in allowable_log_levels_set:
        raise ValueError(f"Invalid RT_LOG_LEVEL: {env_level}")

    env_level = cast(AllowableLogLevels, env_level)  # may the typing police be happy

    _module_logging_config["level"] = env_level
    _module_logging_config["log_file"] = env_log_file

    prepare_logger(
        setting=_module_logging_config["level"], path=_module_logging_config["log_file"]
    )


def configure_module_logging(
    level: AllowableLogLevels | None = None, log_file: str | os.PathLike | None = None
) -> None:
    """
    Configure module-level logging at runtime.

    This updates the logging configuration for the entire railtracks module.
    Changes apply immediately and persist for the lifetime of the Python process.

    If a Session is currently active with custom logging settings, this will
    not affect that session. The new configuration will apply after the session ends.

    Args:
        level: The logging level to use (SILENT, REGULAR, DEBUG, VERBOSE)
        log_file: Optional path to a log file. If None, logs only to console.
    """

    global _module_logging_config

    _module_logging_config["level"] = level
    _module_logging_config["log_file"] = log_file

    _pre__config = {
        "level": _module_logging_config["level"],
        "log_file": _module_logging_config["log_file"],
    }

    if not _session_has_override:
        prepare_logger(
            setting=level
            if level is not None
            else cast(AllowableLogLevels, _module_logging_config["level"]),
            path=_module_logging_config["log_file"],
        )


def mark_session_logging_override(
    session_level: AllowableLogLevels, session_log_file: str | os.PathLike | None
) -> None:
    """
    Mark that a session has overridden module-level logging.

    Stores the current module config for later restoration and applies
    the session-specific logging configuration.

    Args:
        session_level: The session's logging level
        session_log_file: The session's log file (or None)
    """
    global _session_has_override, _pre_session_config

    _pre_session_config = {
        "level": _module_logging_config["level"],
        "log_file": _module_logging_config["log_file"],
    }
    _session_has_override = True

    prepare_logger(setting=session_level, path=session_log_file)


def restore_module_logging() -> None:
    """
    Restore module-level logging after a session with custom logging ends.

    This detaches the session's logging handlers and restores the module-level
    configuration that was in place before the session started.
    """
    global _session_has_override, _pre_session_config

    if not _session_has_override:
        return

    detach_logging_handlers()

    if _pre_session_config is not None:
        prepare_logger(
            setting=cast(AllowableLogLevels, _pre_session_config["level"]),
            path=_pre_session_config["log_file"],
        )
    else:
        # Fallback
        prepare_logger(setting=AllowableLogLevels.REGULAR, path=None)

    _session_has_override = False
    _pre_session_config = {}
