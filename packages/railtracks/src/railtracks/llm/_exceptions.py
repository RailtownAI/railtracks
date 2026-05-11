class RTLLMError(Exception):
    """
    A simple base class for all LLM Exceptions to inherit from.
    """

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


class RetryError(RTLLMError):
    """
    Raised when an error occurs during an LLM call that is being retried.
    """

    def __init__(
        self,
        retry_method: str,
        message: str,
        notes: list[str],
        exception_list: list[Exception],
    ):
        full_message = (
            f"LLM call failed after retries from {retry_method} retry: {message}"
        )
        self.message = message
        self.notes = notes
        self.exception_list = exception_list
        super().__init__(full_message)
