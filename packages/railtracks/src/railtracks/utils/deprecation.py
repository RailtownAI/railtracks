"""Notices for APIs that change in the next railtracks release.

Railtracks 1.5.0 removes or relocates a number of public APIs. Because 1.5.0 is a
*minor* release, version pins such as ``railtracks>=1.4`` or ``railtracks~=1.4`` pick it
up automatically.

These notices are emitted as :class:`FutureWarning` as they are supposed to show
changes that affect end users.

Notice guides:
- Warn where **user code** enters the framework, never on an internal call path. A
  notice that fires during railtracks' own imports or on every node invocation is
  mis-sited.
- Prefer build time over call time (e.g. when an agent is created, not each `invoke`).
- Only pass ``instead`` when the replacement is importable in *this* release.
"""

from __future__ import annotations

import warnings

NEXT_VERSION = "1.5.0"
UPGRADE_GUIDE = "https://docs.railtracks.org/documentation/upgrading/1_5_0/"


def warn_pending_change(
    what: str,
    *,
    change: str = "changes",
    instead: str | None = None,
    detail: str | None = None,
    stacklevel: int = 3,
) -> None:
    """Emit a ``FutureWarning`` about an API that changes in the next release.

    Args:
        what: The API that is changing, spelled the way a user writes it
            (e.g. ``"rt.interactive"``).
        change: Verb phrase describing the change, e.g. ``"is removed"`` or ``"moves"``.
        instead: The replacement to use. Only pass this when the replacement already
            works in the current release; omit it when no forward path exists yet, and
            the message will point at the upgrade guide instead.
        detail: Extra context appended before the guide link.
        stacklevel: Frames to skip so the warning is attributed to the user's line. The
            default of 3 is correct for a helper called from a module-level
            ``__getattr__`` or from a public function body.
    """
    message = f"{what} {change} in railtracks {NEXT_VERSION}."

    if instead is not None:
        message += f" Use {instead} instead."
    if detail is not None:
        message += f" {detail}"

    message += f" See {UPGRADE_GUIDE} for the full upgrade guide."

    warnings.warn(message, FutureWarning, stacklevel=stacklevel)
