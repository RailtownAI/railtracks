"""Errors raised by ``railtracks.decisions``.

Two independent roots, mirroring the ``llm`` package: ``DecisionProviderError`` for a failed
call to a decision model (the counterpart of ``ProviderError``), and
``SchemaDefinitionError`` for a schema or question defined wrongly (the counterpart of
``ToolCreationError``). Neither is an ``RTError``: inside a ``decision_node`` the
invoker turns a ``DecisionProviderError`` into the matching ``DecisionModelError``.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .schema import DecisionAnswer


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


class DecisionProviderError(_NotedError):
    """A call to a decision model failed. Raised only by direct model calls.

    Raised as is for a failure no subclass covers: a dropped connection, a 5xx or
    other 4xx status or a response that could not be parsed.

    ``retry_exhausted`` marks a spent retry budget; ``retry_errors`` keeps the
    attempts so outer retry layers can propagate the failure without retrying it.
    """

    retry_exhausted: bool = False
    retry_errors: tuple[Exception, ...] = ()


class DecisionProviderTimeoutError(DecisionProviderError):
    """The model did not answer in time. Usually transient."""


class DecisionProviderRateLimitError(DecisionProviderError):
    """The host rejected the call for rate or quota reasons. Worth backing off."""


class DecisionProviderAuthenticationError(DecisionProviderError):
    """The API key is missing or was rejected. Retrying will not help."""


class DecisionProviderRefusalError(DecisionProviderError):
    """The model declined to answer one or more questions. Retrying will not help.

    Attributes:
        refused: The names of the questions the model declined.
        answers: The answers it did give, keyed by question name.
    """

    def __init__(
        self,
        reason: str,
        refused: list[str],
        answers: Mapping[str, DecisionAnswer],
        notes: list[str] | None = None,
    ):
        super().__init__(reason, notes=notes)
        self.refused = list(refused)
        self.answers = dict(answers)


class SchemaDefinitionError(_NotedError):
    """A schema or question was defined wrongly. A bug in the caller's code."""
