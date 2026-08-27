from typing import TYPE_CHECKING

from ._base import RTError

if TYPE_CHECKING:
    from railtracks.llm.history import MessageHistory

__all__ = [
    "RTError",
    "NodeInvocationError",
    "NodeCreationError",
    "LLMError",
    "LLMTimeoutError",
    "LLMRateLimitError",
    "LLMAuthenticationError",
    "GlobalTimeOutError",
    "ContextError",
    "FatalError",
]


class NodeInvocationError(RTError):
    """
    Raised during node for execution problems in graph, including node or orchestration failures.
    For example, bad config, missing required parameters, or structural errors.
    """

    def __init__(
        self,
        message: str | None = None,
        notes: list[str] | None = None,
        fatal: bool = False,
    ):
        super().__init__(message)
        self.notes = notes or []
        self.fatal = fatal

    def __str__(self):
        base = super().__str__()
        if self.notes:
            notes_str = (
                "\n"
                + self._color("Tips to debug:\n", self.GREEN)
                + "\n".join(self._color(f"- {note}", self.GREEN) for note in self.notes)
            )
            return f"\n{self._color(base, self.RED)}{notes_str}"
        return self._color(base, self.RED)


class LLMError(NodeInvocationError):
    """
    Raised when a node terminates because the LLM layer failed.

    The originating `railtracks.llm` error is preserved on `__cause__`.

    Being a `NodeInvocationError` lets callers branch on both axes at once: catch
    `NodeInvocationError` for "a node terminated", then test for `LLMError` to ask
    whether the LLM caused it.
    """

    def __init__(
        self,
        reason: str,
        message_history: "MessageHistory | None" = None,
        notes: list[str] | None = None,
        fatal: bool = False,
    ):
        self.reason = reason
        self.message_history = message_history

        message = f"{self._color('LLM Error: ', self.BOLD_RED)}{self._color(reason, self.RED)}"
        super().__init__(message, notes=notes, fatal=fatal)

    def __str__(self):
        # Bypasses NodeInvocationError.__str__ so the base message is not coloured twice.
        base = Exception.__str__(self)
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
        if self.notes:
            details.append(
                self._color("Tips to debug:\n", self.BOLD_GREEN)
                + "\n".join(
                    self._color(f"    - {note}", self.GREEN) for note in self.notes
                )  # match the message history block's indent
            )
        if details:
            notes_str = (
                "\n"
                + self._color("Details:\n", self.BOLD_GREEN)
                + "\n".join(f"  {d}" for d in details)
            )
            return f"\n{self._color(base, self.RED)}{notes_str}"
        return self._color(base, self.RED)


class LLMTimeoutError(LLMError):
    """The model did not answer in time.

    Not a builtin `TimeoutError`, matching `GlobalTimeOutError`, so that no `except`
    clause catches one Railtracks timeout and misses the other.
    """


class LLMRateLimitError(LLMError):
    """The provider rejected the call for rate or quota reasons. Usually worth backing off."""


class LLMAuthenticationError(LLMError):
    """The provider rejected the credentials. Retrying will not help; fix the config."""


class NodeCreationError(RTError):
    """
    Raised during node creation/validation before any execution begins.
    For example, bad config, missing required parameters, or structural errors.
    """

    def __init__(self, message=None, notes=None):
        if message is None:
            message = "Something went wrong during node creation."
        super().__init__(message)
        self.notes = notes or []

    def __str__(self):
        base = super().__str__()
        if self.notes:
            notes_str = (
                "\n"
                + self._color("Tips to debug:\n", self.GREEN)
                + "\n".join(self._color(f"- {note}", self.GREEN) for note in self.notes)
            )
            return f"\n{self._color(base, self.RED)}{notes_str}"
        return self._color(base, self.RED)


class GlobalTimeOutError(RTError):
    """
    Raised on global timeout for whole execution.
    """

    def __init__(self, timeout: float):
        self.message = f"Execution timed out after {timeout} seconds"
        self.timeout = timeout
        super().__init__(self.message)

    def __str__(self):
        return self._color(self.message, self.RED)


class ContextError(RTError):
    """
    Raised when there is an error with the context.
    """

    def __init__(self, message: str = None, notes: list[str] = None):
        self.message = message or "Context error"
        self.notes = notes or []
        super().__init__(self.message)

    def __str__(self):
        base = super().__str__()
        if self.notes:
            notes_str = (
                "\n"
                + self._color("Tips to debug:\n", self.GREEN)
                + "\n".join(self._color(f"- {note}", self.GREEN) for note in self.notes)
            )
            return f"\n{self._color(base, self.RED)}{notes_str}"
        return self._color(base, self.RED)


class FatalError(RTError):
    pass
