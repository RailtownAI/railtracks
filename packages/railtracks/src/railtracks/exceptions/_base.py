import sys


class RTError(Exception):
    """
    A simple base class for all RTExceptions to inherit from.
    """

    # whether the error stops the whole run on its own, whatever the run's config
    fatal: bool = False

    # ANSI color codes for terminal output
    BOLD_RED = "\033[1m\033[91m"
    RED = "\033[91m"
    BOLD_GREEN = "\033[1m\033[92m"
    GREEN = "\033[92m"
    RESET = "\033[0m"

    @classmethod
    def _color(cls, text, color_code):
        """Colours text for a terminal; leaves it plain when stderr is redirected (a log
        file, CI), so the codes don't end up there."""
        if not _stderr_is_terminal():
            return str(text)
        return f"{color_code}{text}{cls.RESET}"


def is_fatal(exc: BaseException) -> bool:
    """Whether ``exc`` stops the whole run on its own. Only railtracks errors can, so
    another library's ``fatal`` attribute is never mistaken for this flag."""
    return isinstance(exc, RTError) and exc.fatal


def _stderr_is_terminal() -> bool:
    try:
        return sys.stderr.isatty()
    except (AttributeError, ValueError):
        # no stderr at all (pythonw), or one that has been closed
        return False
