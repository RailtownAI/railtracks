from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class Verdict:
    """The result of an approve callable's review of a node call.

    - accept: ``accepted=True``, ``comment=None``
    - accept with comments: ``accepted=True``, ``comment=<str>``, optionally
      ``args``/``kwargs`` (pre-call) or ``result`` (post-call) set to override
      what gets forwarded.
    - decline: ``accepted=False``, ``comment=None``
    - decline with comments: ``accepted=False``, ``comment=<str>``

    ``args``/``kwargs`` mean "forward these into the call instead" -- used by
    pre-call verifiers, which review before the node runs. ``result`` means
    "propagate this instead of what the call produced" -- used by post-call
    verifiers, which review after the node has already run and can no longer
    change what was passed in, only what continues onward.

    Overridden ``args``/``kwargs``/``result`` are forwarded as-is, with no
    validation against the node's original signature or return type -- a bad
    override surfaces as a ``TypeError`` from the node call itself, or
    propagates silently if it happens to satisfy downstream expectations.
    """

    accepted: bool
    comment: str | None = None
    args: tuple | None = None
    kwargs: dict | None = None
    result: Any | None = None


class VerifierRejectedError(Exception):
    """Raised when a verifier's approve callable declines a node call."""
