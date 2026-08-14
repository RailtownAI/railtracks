"""LLM-level guardrails.

The concrete prebuilt guards and the PII configuration classes are **relocating** to
``rt.prebuilt.guardrails`` in railtracks 1.5.0, where they are already available today.
Accessing them from here still works in this release but emits a ``FutureWarning``.

The authoring bases ``InputGuard`` / ``OutputGuard`` and the decision types are not
moving; keep importing those from ``rt.guardrails``.
"""

from __future__ import annotations

import importlib
from typing import TYPE_CHECKING

from railtracks.utils.deprecation import warn_pending_change

from .mixin import LLMGuardrailsMixin

if TYPE_CHECKING:
    # Redundant aliases mark these as intentional re-exports, so type checkers still
    # resolve the deprecated spellings even though `__all__` no longer advertises them.
    from . import input as input
    from . import output as output
    from ._pii.config import PIICustomPattern as PIICustomPattern
    from ._pii.config import PIIEntity as PIIEntity
    from ._pii.config import PIIRedactConfig as PIIRedactConfig
    from .input.block_text import BlockTextInputGuard as BlockTextInputGuard
    from .input.length_guard import InputLengthGuard as InputLengthGuard
    from .input.pii_redact import PIIRedactInputGuard as PIIRedactInputGuard
    from .output.block_text import BlockTextOutputGuard as BlockTextOutputGuard
    from .output.length_guard import OutputLengthGuard as OutputLengthGuard
    from .output.pii_redact import PIIRedactOutputGuard as PIIRedactOutputGuard

# The relocated names now live in `rt.prebuilt.guardrails`
__all__ = [
    "LLMGuardrailsMixin",
]

# name -> module (relative to this package) it is defined in.
_RELOCATED: dict[str, str] = {
    "BlockTextInputGuard": ".input.block_text",
    "InputLengthGuard": ".input.length_guard",
    "PIIRedactInputGuard": ".input.pii_redact",
    "BlockTextOutputGuard": ".output.block_text",
    "OutputLengthGuard": ".output.length_guard",
    "PIIRedactOutputGuard": ".output.pii_redact",
    "PIICustomPattern": "._pii.config",
    "PIIEntity": "._pii.config",
    "PIIRedactConfig": "._pii.config",
}


def __getattr__(name: str):
    if name in _RELOCATED:
        warn_pending_change(
            f"rt.guardrails.llm.{name}",
            change="moves",
            instead=f"rt.prebuilt.guardrails.{name}",
            detail="The class itself is unchanged.",
        )
        module = importlib.import_module(_RELOCATED[name], __name__)
        return getattr(module, name)

    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__() -> list[str]:
    return sorted([*__all__, *_RELOCATED])
