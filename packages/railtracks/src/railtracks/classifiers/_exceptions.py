"""Errors raised by ``railtracks.classifiers``.

Two independent roots, mirroring the ``llm`` package: ``ClassifierError`` for a failed
call to a decision model (the counterpart of ``ProviderError``), and
``SchemaDefinitionError`` for a schema or question defined wrongly (the counterpart of
``ToolCreationError``). Neither is an ``RTError``: inside a ``decision_node`` the
invoker turns a ``ClassifierError`` into the matching ``DecisionModelError``.
"""

from __future__ import annotations


class _NotedError(Exception):
    """An error with a ``reason`` and optional debugging ``notes``."""

    def __init__(self, reason: str, notes: list[str] | None = None) -> None:
        super().__init__(reason)
        self.reason = reason
        self.notes = list(notes) if notes is not None else []

    def __str__(self) -> str:
        if not self.notes:
            return self.reason
        tips = "\n".join(f"- {note}" for note in self.notes)
        return f"{self.reason}\nTips to debug:\n{tips}"


class ClassifierError(_NotedError):
    """A call to a decision model failed. Raised only by direct model calls."""


class ClassifierTimeoutError(ClassifierError):
    """The model did not answer in time. Usually transient."""


class ClassifierConnectionError(ClassifierError):
    """The server could not be reached, or dropped the connection. Usually transient."""


class ClassifierRateLimitError(ClassifierError):
    """The host rejected the call for rate or quota reasons. Worth backing off."""


class ClassifierServerError(ClassifierError):
    """The host failed with a 5xx status. Usually transient."""


class ClassifierAuthenticationError(ClassifierError):
    """The API key is missing or was rejected. Retrying will not help."""


class ClassifierRequestError(ClassifierError):
    """The request was rejected or could not be sent: a 4xx other than auth or rate
    limits, a host limit exceeded, or a malformed ``api_base``. Retrying will not help.
    """

    def __init__(self, reason: str, body: str = "", notes: list[str] | None = None):
        super().__init__(reason, notes=notes)
        self.body = body


class ClassifierResponseError(ClassifierError):
    """The host's response could not be parsed into answers."""


class SchemaDefinitionError(_NotedError):
    """A schema or question was defined wrongly. A bug in the caller's code."""
