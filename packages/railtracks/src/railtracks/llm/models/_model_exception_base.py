from .._exceptions import ProviderError
from ..history import MessageHistory


class ModelError(ProviderError):
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
        if not self.message_history:
            return self._color(base, self.RED)

        try:
            count = len(self.message_history)
        except TypeError:
            count = None

        summary = (
            f"{count} message(s) redacted; "
            "call err.format_verbose() to render or read err.message_history"
            if count is not None
            else "message history redacted; "
            "call err.format_verbose() to render or read err.message_history"
        )
        detail = self._color("Message History: ", self.BOLD_GREEN) + self._color(
            summary, self.GREEN
        )
        notes_str = "\n" + self._color("Details:\n", self.BOLD_GREEN) + f"  {detail}"
        return f"\n{self._color(base, self.RED)}{notes_str}"

    def format_verbose(self) -> str:
        """Render the exception with the full input ``MessageHistory`` embedded."""
        base = super().__str__()
        if not self.message_history:
            return self._color(base, self.RED)

        mh_str = str(self.message_history)
        indented_mh = "\n".join("    " + line for line in mh_str.splitlines())
        detail = self._color("Message History:\n", self.BOLD_GREEN) + self._color(
            indented_mh, self.GREEN
        )
        notes_str = "\n" + self._color("Details:\n", self.BOLD_GREEN) + f"  {detail}"
        return f"\n{self._color(base, self.RED)}{notes_str}"


class ModelNotFoundError(ProviderError):
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


class UnsupportedHyperparameterError(ModelError):
    """Error raised when a model does not support a given common LLM hyperparameter."""

    def __init__(self, model_name: str, hyperparameter: str, value):
        super().__init__(
            reason=(
                f"Model {model_name} does not support '{hyperparameter}' "
                f"(got {hyperparameter}={value!r})."
            )
        )


class MutuallyExclusiveHyperparametersError(ModelError):
    """Error raised when two or more common hyperparameters cannot be combined for
    this model."""

    def __init__(self, model_name: str, hyperparameters: list[str], values: dict):
        joined = " and ".join(f"'{p}'" for p in hyperparameters)
        super().__init__(
            reason=(
                f"Model {model_name} does not support specifying {joined} together "
                f"(got {values!r}). Use only one."
            )
        )
