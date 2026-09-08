from __future__ import annotations

from dataclasses import dataclass
from typing import Generic, TypeVar

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
