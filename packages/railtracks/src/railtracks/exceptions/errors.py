from ._base import RTError


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
