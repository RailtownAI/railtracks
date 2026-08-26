from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .history import MessageHistory


class RTLLMError(Exception):
    """
    A simple base class for all LLM Exceptions to inherit from.

    The ``llm`` package is self-contained and never imports from the rest of
    ``railtracks``, so it owns its own exception root rather than sharing
    ``railtracks.exceptions.RTError``.
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


class LLMError(RTLLMError):
    """
    Raised when an error occurs during LLM invocation or completion.
    """

    def __init__(
        self,
        reason: str,
        message_history: "MessageHistory" = None,
    ):
        self.reason = reason
        self.message_history = message_history

        message = f"{self._color('LLM Error: ', self.BOLD_RED)}{self._color(reason, self.RED)}"
        super().__init__(message)

    def __str__(self):
        base = super().__str__()
        details = []
        if self.message_history:
            mh_str = str(self.message_history)
            indented_mh = "\n".join(
                "    " + line for line in mh_str.splitlines()
            )  # 2 indents (2-spaces) per indent
            details.append(
                self._color("Message History:\n", self.BOLD_GREEN)
                + self._color(indented_mh, self.GREEN)
            )
        if details:
            notes_str = (
                "\n"
                + self._color("Details:\n", self.BOLD_GREEN)
                + "\n".join(f"  {d}" for d in details)
            )
            return f"\n{self._color(base, self.RED)}{notes_str}"
        return self._color(base, self.RED)


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
