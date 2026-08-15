from __future__ import annotations

from ._astream import astream
from ._call import call
from .batch import call_batch
from .broadcast_ import broadcast
from .couple import couple

__all__ = [
    "call",
    "call_batch",
    "astream",
    "broadcast",
    "couple",
]


def __getattr__(name: str):
    if name == "local_chat":
        from railtracks.utils.deprecation import warn_pending_change

        warn_pending_change(
            "local_chat",
            change="is removed",
            detail="There is no replacement; the local chat UI is going away.",
        )
        from .interactive import local_chat

        return local_chat
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__() -> list[str]:
    return sorted(set(__all__))
