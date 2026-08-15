"""Prebuilt output guards.

These relocate to ``rt.prebuilt.guardrails`` in railtracks 1.5.0, where they are already
available today. Pulling them from this package still works but emits a
``FutureWarning``.
"""

from __future__ import annotations

import importlib
from typing import TYPE_CHECKING

from railtracks.utils.deprecation import warn_pending_change

if TYPE_CHECKING:
    from .block_text import BlockTextOutputGuard as BlockTextOutputGuard
    from .length_guard import OutputLengthGuard as OutputLengthGuard
    from .pii_redact import PIIRedactOutputGuard as PIIRedactOutputGuard


__all__: list[str] = []

_RELOCATED = {
    "BlockTextOutputGuard": ".block_text",
    "OutputLengthGuard": ".length_guard",
    "PIIRedactOutputGuard": ".pii_redact",
}


def __getattr__(name: str):
    if name in _RELOCATED:
        warn_pending_change(
            f"rt.guardrails.llm.output.{name}",
            change="moves",
            instead=f"rt.prebuilt.guardrails.{name}",
            detail="The class itself is unchanged.",
        )
        module = importlib.import_module(_RELOCATED[name], __name__)
        return getattr(module, name)

    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__() -> list[str]:
    return sorted([*__all__, *_RELOCATED])
