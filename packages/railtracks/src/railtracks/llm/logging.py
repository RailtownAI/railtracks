"""Logging utilities for the LLM module."""

import logging

from colorama import Fore, Style, init

# Initialize colorama
init(autoreset=True)


class ColoredFormatter(logging.Formatter):
    """Custom formatter for colored log output.

    Applies colors based on log level:
    - WARNING: Yellow
    - ERROR: Red
    - CRITICAL: Bright Red
    """

    COLORS = {
        logging.WARNING: Fore.YELLOW,
        logging.ERROR: Fore.RED,
        logging.CRITICAL: Fore.RED + Style.BRIGHT,
    }

    def format(self, record):
        log_color = self.COLORS.get(record.levelno, "")
        if log_color:
            record.levelname = f"{log_color}{record.levelname}{Style.RESET_ALL}"
            record.msg = f"{log_color}{record.msg}{Style.RESET_ALL}"
        return super().format(record)


def setup_logger(name: str, level: int = logging.WARNING) -> logging.Logger:
    """Set up a logger with colored output.

    Args:
        name: The name of the logger. Will be prefixed with "LLM." and the last component
              will be extracted (e.g., "railtracks.llm.models.local.ollama" becomes "LLM.Ollama").
        level: The logging level (default: logging.WARNING).

    Returns:
        Configured logger instance.
    """
    # Extract the last component of the module name and capitalize it
    module_name = name.split(".")[-1].capitalize()
    logger_name = f"LLM.{module_name}"

    logger = logging.getLogger(logger_name)

    # Only add handler if logger doesn't have one yet
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(ColoredFormatter("%(name)s : %(levelname)s - %(message)s"))
        logger.addHandler(handler)
        logger.setLevel(level)

    return logger
