from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Generic, TypeVar

from pydantic import BaseModel

_R = TypeVar("_R")


@dataclass
class Verdict(Generic[_R]):
    """The result of an approve callable's review of a node call.

    - accept: ``accepted=True``, ``comment=None``
    - accept with comments: ``accepted=True``, ``comment=<str>``, optionally
      ``args``/``kwargs`` (pre-call) or ``result`` (post-call) set to override
      what gets forwarded.
    - decline: ``accepted=False``, ``comment=None``
    - decline with comments: ``accepted=False``, ``comment=<str>``

    ``args``/``kwargs`` mean "forward these into the call instead" — used by
    pre-call verifiers, which review before the node runs. ``result`` means
    "propagate this instead of what the call produced" — used by post-call
    verifiers, which review after the node has already run and can no longer
    change what was passed in, only what continues onward.

    ``Verdict`` is generic over ``result``'s type, matching the wrapped
    node's return type, so a ``result=`` override of the wrong type is a
    type-checker error rather than a silent runtime mismatch. There is no
    runtime validation of ``args``/``kwargs`` overrides against the node's
    signature — a bad override surfaces as a ``TypeError`` from the call
    itself.
    """

    accepted: bool
    comment: str | None = None
    args: tuple | None = None
    kwargs: dict | None = None
    result: _R | None = None


class VerifierRejectedError(Exception):
    """Raised when a verifier's approve callable declines a node call."""


class VerifierAction(str, Enum):
    """What a verifier's review concluded.

    Members:
        ACCEPT: The call (or its output) may proceed.
        DECLINE: The call (or its output) is rejected.
    """

    ACCEPT = "accept"
    DECLINE = "decline"


class VerifierDecision(BaseModel):
    """Structured, observable summary of a `Verdict`, carried on verifier events.

    Mirrors `GuardrailDecision`'s shape so verifier decisions are tagged in the
    trace the same way guardrail decisions are.

    Attributes:
        action: Whether the verdict accepted or declined the call.
        reason: The verdict's comment, if any.
        overridden: Whether the verdict replaced args/kwargs (pre-call) or the
            result (post-call) instead of forwarding them unchanged.
        timeout: Whether this decision was synthesized because `approve_fn`
            didn't respond within the configured timeout, rather than an
            actual verdict from `approve_fn` itself.
    """

    action: VerifierAction
    reason: str | None = None
    overridden: bool = False
    timeout: bool = False

    @classmethod
    def from_verdict(
        cls, verdict: Verdict, *, overridden: bool, timeout: bool = False
    ) -> "VerifierDecision":
        """Build a `VerifierDecision` summarizing `verdict`."""
        return cls(
            action=VerifierAction.ACCEPT
            if verdict.accepted
            else VerifierAction.DECLINE,
            reason=verdict.comment,
            overridden=overridden,
            timeout=timeout,
        )
