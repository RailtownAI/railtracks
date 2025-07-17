class RCError(Exception):
    """
    A simple base class for all RCExceptions to inherit from.
    """

    # ANSI color codes for terminal output
    BOLD_RED = "\033[1m\033[91m"
    RED = "\033[91m"
    BOLD_GREEN = "\033[1m\033[92m"
    GREEN = "\033[92m"
    RESET = "\033[0m"

    @classmethod
    def _color(cls, text, color_code):
        return f"{color_code}{text}{cls.RESET}"
