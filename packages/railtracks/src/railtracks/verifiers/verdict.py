from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Verdict:
    """The result of an approve callable's review of a node call.

    - accept: ``accepted=True``, ``comment=None``
    - accept with comments: ``accepted=True``, ``comment=<str>``, optionally
      ``args``/``kwargs`` set to rewrite what gets forwarded to the node.
    - decline: ``accepted=False``, ``comment=None``
    - decline with comments: ``accepted=False``, ``comment=<str>``

    Overridden ``args``/``kwargs`` are forwarded as-is, with no validation
    against the node's original signature — a bad override surfaces as a
    ``TypeError`` from the node call itself.
    """

    accepted: bool
    comment: str | None = None
    args: tuple | None = None
    kwargs: dict | None = None
