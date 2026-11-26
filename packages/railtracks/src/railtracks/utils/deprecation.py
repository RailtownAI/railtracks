"""Notices for public APIs that change or go away in a future railtracks release.

``warn_pending_change`` emits a single notice and ``renamed_kwargs`` keeps renamed
keyword arguments working under their old names. Each notice names the release that
makes the change: ``NEXT_VERSION`` (1.5.0, which removes or relocates a number of
public APIs) unless the caller passes another, such as 2.0.0 for renamed arguments.
Because 1.5.0 is a *minor* release, version pins such as ``railtracks>=1.4`` or
``railtracks~=1.4`` pick it up automatically.

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

import functools
import inspect
import warnings
from collections.abc import Callable
from typing import ParamSpec, TypeVar

P = ParamSpec("P")
R = TypeVar("R")

NEXT_VERSION = "1.5.0"
UPGRADE_GUIDE = "https://docs.railtracks.org/documentation/upgrading/1_5_0/"


def warn_pending_change(
    what: str,
    *,
    change: str = "changes",
    instead: str | None = None,
    detail: str | None = None,
    version: str | None = None,
    guide: str = UPGRADE_GUIDE,
    stacklevel: int = 3,
) -> None:
    """Emit a ``FutureWarning`` about an API that changes in the next release.

    Args:
        what: The API that is changing, spelled the way a user writes it
            (e.g. ``"rt.after_node"``).
        change: Verb phrase describing the change, e.g. ``"is removed"`` or ``"moves"``.
        instead: The replacement to use. Only pass this when the replacement already
            works in the current release; omit it when no forward path exists yet, and
            the message will point at the upgrade guide instead.
        detail: Extra context appended before the guide link.
        version: The release the change lands in. Defaults to ``NEXT_VERSION``.
        guide: The docs URL the message links to. Defaults to the 1.5.0 upgrade guide.
        stacklevel: Frames to skip so the warning is attributed to the user's line. The
            default of 3 is correct for a helper called from a module-level
            ``__getattr__`` or from a public function body.
    """
    message = f"{what} {change} in railtracks {version or NEXT_VERSION}."

    if instead is not None:
        message += f" Use {instead} instead."
    if detail is not None:
        message += f" {detail}"

    message += f" See {guide} for details."

    warnings.warn(message, FutureWarning, stacklevel=stacklevel)


def renamed_kwargs(
    *, version: str | None = None, guide: str = UPGRADE_GUIDE, **renames: str
) -> Callable[[Callable[P, R]], Callable[P, R]]:
    """Accept the old names of renamed keyword arguments, warning when one is used.

    Decorate a function, usually ``__init__``, with ``old_name="new_name"`` pairs. A
    call that passes ``old_name=`` warns and is forwarded as ``new_name=``. The
    decorated signature only lists the new names, so required arguments stay required.

    Args:
        version: The release that removes the old names. Defaults to ``NEXT_VERSION``.
        guide: The docs URL the warning links to. Defaults to the 1.5.0 upgrade guide.
        **renames: Each old keyword name mapped to its new name.

    Raises:
        TypeError: At call time, if a call passes both an old name and its new name,
            whether the new one is given by keyword or by position.
    """

    def decorate(func: Callable[P, R]) -> Callable[P, R]:
        owner = func.__qualname__.removesuffix(".__init__")
        signature = inspect.signature(func)

        @functools.wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            for old, new in renames.items():
                if old not in kwargs:
                    continue
                if new in kwargs or new in signature.bind_partial(*args).arguments:
                    raise TypeError(
                        f"{owner}() got both {old}= and {new}=; pass only {new}=."
                    )
                warn_pending_change(
                    f"{owner}({old}=...)",
                    change="is removed",
                    instead=f"{new}=",
                    version=version,
                    guide=guide,
                )
                kwargs[new] = kwargs.pop(old)
            return func(*args, **kwargs)

        return wrapper

    return decorate
