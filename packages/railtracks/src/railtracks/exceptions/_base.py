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
        """A simple helper method to colorize text for output."""
        return f"{color_code}{text}{cls.RESET}"
