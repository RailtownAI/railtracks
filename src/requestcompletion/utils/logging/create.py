import logging

from .config import rc_logger_name


def get_rc_logger(name: str | None = None):
    """
    A method used to get a logger of the provided name.

    The method is essentially a wrapper of the `logging` method to collect the logger, but it will add a reference to
    the RC root logger.

    If the name is not provided it returns the root RC logger.
    """
    if name is None:
        return logging.getLogger(rc_logger_name)

    logger = logging.getLogger(f"{rc_logger_name}.{name}")

    return logger
