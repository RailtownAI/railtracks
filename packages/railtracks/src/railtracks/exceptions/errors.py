from typing import TYPE_CHECKING

from ._base import RTError

if TYPE_CHECKING:
    from railtracks.llm.history import MessageHistory


class NodeInvocationError(RTError):
    """
    Raised during node for execution problems in graph, including node or orchestration failures.
    For example, bad config, missing required parameters, or structural errors.
    """

    def __init__(
        self, message: str = None, notes: list[str] = None, fatal: bool = False
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


class LLMError(RTError):
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
        if not self.message_history:
            return self._color(base, self.RED)

        # Lazy import to keep the exceptions module free of a hard logging dep.
        from railtracks.utils.logging.config import verbose_llm_errors

        try:
            count = len(self.message_history)
        except TypeError:
            count = None

        if verbose_llm_errors():
            mh_str = str(self.message_history)
            indented_mh = "\n".join("    " + line for line in mh_str.splitlines())
            detail = self._color("Message History:\n", self.BOLD_GREEN) + self._color(
                indented_mh, self.GREEN
            )
        else:
            summary = (
                f"{count} message(s) redacted; "
                "enable via rt.enable_logging(verbose_llm_errors=True)"
                if count is not None
                else "message history redacted; "
                "enable via rt.enable_logging(verbose_llm_errors=True)"
            )
            detail = self._color("Message History: ", self.BOLD_GREEN) + self._color(
                summary, self.GREEN
            )

        notes_str = "\n" + self._color("Details:\n", self.BOLD_GREEN) + f"  {detail}"
        return f"\n{self._color(base, self.RED)}{notes_str}"


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
