import logging

from railtracks.context.central import RTContextLoggingAdapter

from .config import rt_logger_name


def get_rt_logger(name: str | None = None):
    """
    A method used to get a logger of the provided name.

    The method is essentially a wrapper of the `logging` method to collect the logger, but it will add a reference to
    the RT root logger.

    If the name is not provided it returns the root RT logger.
    """
    if name is None:
        logger = logging.getLogger(rt_logger_name)
    else:
        logger = logging.getLogger(f"{rt_logger_name}.{name}")

    adapter = RTContextLoggingAdapter(logger, {})
    return adapter
