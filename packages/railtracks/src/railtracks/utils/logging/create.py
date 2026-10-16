import logging

from railtracks.context.central import RTContextLoggingAdapter

from .config import lifecycle_logger_name, rt_logger_name


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


def get_lifecycle_logger():
    """
    The logger for node creation, completion, and failure records.

    Railtracks' console leaves these to the run view; every other handler on the RT
    logger, the root logger, or this one still receives them.
    """
    return RTContextLoggingAdapter(logging.getLogger(lifecycle_logger_name), {})
