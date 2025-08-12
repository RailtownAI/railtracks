from .._exception_base import RTLLMError
from ..history import MessageHistory


class ModelError(RTLLMError):
    """
    Any Large Language Model (LLM) error.
    """

    def __init__(
        self,
        reason: str,
        message_history: MessageHistory = None,
    ):
        self.reason = reason
        self.message_history = message_history

        message = f"{self._color('Failure reason: ', self.BOLD_RED)}{self._color(reason, self.RED)}"
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


class ModelNotFoundError(RTLLMError):
    def __init__(self, reason: str, notes: list[str] = None):
        self.reason = reason
        self.notes = notes or []
        super().__init__(reason)

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


class FunctionCallingNotSupportedError(ModelError):
    """Error raised when a model does not support function calling."""

    def __init__(self, model_name: str):
        super().__init__(
            reason=f"Model {model_name} does not support function calling. Chat with tools is not supported."
        )
