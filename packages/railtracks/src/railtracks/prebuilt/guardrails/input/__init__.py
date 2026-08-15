"""Prebuilt input guards.

These relocate to ``rt.prebuilt.guardrails`` in railtracks 1.5.0, where they are already
available today. Pulling them from this package still works but emits a
``FutureWarning``.
"""

from __future__ import annotations

import importlib
from typing import TYPE_CHECKING

from railtracks.utils.deprecation import warn_pending_change

if TYPE_CHECKING:
    from .block_text import BlockTextInputGuard as BlockTextInputGuard
    from .length_guard import InputLengthGuard as InputLengthGuard
    from .pii_redact import PIIRedactInputGuard as PIIRedactInputGuard


__all__: list[str] = []

_RELOCATED = {
    "BlockTextInputGuard": ".block_text",
    "InputLengthGuard": ".length_guard",
    "PIIRedactInputGuard": ".pii_redact",
}


def __getattr__(name: str):
    if name in _RELOCATED:
        warn_pending_change(
            f"rt.guardrails.llm.input.{name}",
            change="moves",
            instead=f"rt.prebuilt.guardrails.{name}",
            detail="The class itself is unchanged.",
        )
        module = importlib.import_module(_RELOCATED[name], __name__)
        return getattr(module, name)

    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__() -> list[str]:
    return sorted([*__all__, *_RELOCATED])
