from __future__ import annotations


class _ColoredError:
    """Terminal colouring shared by this package's error roots.

    Deliberately not an ``Exception`` subclass: mixing it in gives the roots their
    formatting without giving them a common ancestor, so ``except ProviderError``
    cannot accidentally swallow a ``ToolCreationError``.
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


class ProviderError(_ColoredError, Exception):
    """
    Base class for failures that happen while talking to a model provider.

    Covers the model itself misbehaving, an unknown model, and exhausted retries.
    Errors about *defining* a tool are deliberately not part of this hierarchy -- see
    :class:`railtracks.llm.tools.tool.ToolCreationError`.

    The ``llm`` package is self-contained and never imports from the rest of
    ``railtracks``, so it owns this root rather than sharing
    ``railtracks.exceptions.RTError``. Inside a node these are translated once, at the
    ``built_nodes.llm.llm_helpers`` boundary, into `railtracks.exceptions.LLMError`.
    """


class ProviderTimeoutError(ProviderError):
    """The provider did not answer in time."""


class ProviderRateLimitError(ProviderError):
    """The provider rejected the call for rate/quota reasons."""


class ProviderAuthenticationError(ProviderError):
    """The provider rejected the credentials. Retrying will not help."""


class RetryError(ProviderError):
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
