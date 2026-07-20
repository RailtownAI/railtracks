from __future__ import annotations

from typing import TYPE_CHECKING

from ._call import call
from .batch import call_batch
from .broadcast_ import broadcast
from .couple import couple

__all__ = [
    "call",
    "call_batch",
    "broadcast",
    "couple",
]


def __getattr__(name: str):
    if name == "local_chat":
        from .interactive import local_chat

        return local_chat
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__() -> list[str]:
    return sorted(set(__all__))
