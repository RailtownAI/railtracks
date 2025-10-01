import logging
import os
import re
from typing import Literal

from colorama import Fore, init

AllowableLogLevels = Literal["VERBOSE", "REGULAR", "QUIET", "NONE"]
allowable_log_levels_set = {"VERBOSE", "REGULAR", "QUIET", "NONE"}

# the temporary name for the logger that RT will use.
rt_logger_name = "RT"
rt_logger = logging.getLogger(rt_logger_name)
rt_logger.setLevel(logging.INFO)

_default_format_string = "%(timestamp_color)s[+%(relative_seconds)-7ss] %(level_color)s%(name)-12s: %(levelname)-8s - %(message)s%(default_color)s %(session_id)s %(run_id)s %(node_id)s"

_file_format_string = "%(asctime)s %(levelname)s - %(message)s"
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


def setup_verbose_logger_config():
    """
    Sets up the logger configuration in verbose mode.

    Specifically that means:
    - The console will log all messages (including debug)
    """
    console_handler = logging.StreamHandler()
    # in the verbose case we would like to use the debug level.
    console_handler.setLevel(logging.DEBUG)

    verbose_formatter = ColorfulFormatter(
        fmt=_default_format_string,
    )

    console_handler.setFormatter(verbose_formatter)

    logger = logging.getLogger(rt_logger_name)
    logger.addHandler(console_handler)
    # only in verbose do we want to handle the debugging logs
    logger.setLevel(logging.DEBUG)


def setup_regular_logger_config():
    """
    Setups the logger in the regular mode. This mode will print all messages except debug messages to the console.
    """
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)

    regular_formatter = ColorfulFormatter(
        fmt=_default_format_string,
    )

    console_handler.setFormatter(regular_formatter)

    logger = logging.getLogger(rt_logger_name)
    logger.addHandler(console_handler)


def setup_quiet_logger_config():
    """
    Set up the logger to only log warning and above messages.
    """
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.WARNING)

    quiet_formatter = ColorfulFormatter(fmt=_default_format_string)

    console_handler.setFormatter(quiet_formatter)

    logger = logging.getLogger(rt_logger_name)
    logger.addHandler(console_handler)


def setup_none_logger_config():
    """
    Set up the logger to print nothing. This can be a useful optimization technique.
    """
    # set up a logger which does not do anything.
    logger = logging.getLogger(rt_logger_name)
    # a slightly hacky way to get it so nothing makes it through
    logger.addFilter(lambda x: False)
    logger.addHandler(logging.NullHandler())


# TODO Complete the file integration.
def setup_file_handler(
    *,
    file_name: str | os.PathLike,
    file_logging_level: logging.DEBUG
    | logging.INFO
    | logging.WARNING
    | logging.ERROR
    | logging.CRITICAL = logging.INFO,
):
    """
    Setups a logger file handler that will log messages to a file with the given name and logging level.
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
    if path is not None:
        setup_file_handler(file_name=path, file_logging_level=logging.INFO)

    # now for each of our predefined settings we will set up the logger.
    if setting == "VERBOSE":
        setup_verbose_logger_config()
    elif setting == "REGULAR":
        setup_regular_logger_config()
    elif setting == "QUIET":
        setup_quiet_logger_config()
    elif setting == "NONE":
        setup_none_logger_config()
    else:
        raise ValueError("Invalid log level setting")


def detach_logging_handlers():
    """
    Shuts down the logging system and detaches all logging handlers.
    """
    # Get the root logger
    rt_logger.handlers.clear()
