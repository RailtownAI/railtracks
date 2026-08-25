"""Deprecated: this package relocates in railtracks 1.5.0.

``Verdict``/``VerifierRejectedError`` move to ``railtracks.middleware``.
``verifier`` moves to ``railtracks.prebuilt.middleware.pre_verifier``, renamed
to sit alongside its new sibling ``post_verifier`` -- behavior unchanged.
Pulling any of these from this package still works but emits a
``FutureWarning``.
"""

from __future__ import annotations

import importlib
from typing import TYPE_CHECKING

from railtracks.utils.deprecation import warn_pending_change

if TYPE_CHECKING:
    from railtracks.middleware import Verdict as Verdict
    from railtracks.middleware import VerifierRejectedError as VerifierRejectedError
    from railtracks.prebuilt.middleware import pre_verifier as verifier  # noqa: F401

__all__: list[str] = []

_RELOCATED = {
    "verifier": ("railtracks.prebuilt.middleware", "pre_verifier"),
    "Verdict": ("railtracks.middleware", "Verdict"),
    "VerifierRejectedError": ("railtracks.middleware", "VerifierRejectedError"),
}


def __getattr__(name: str):
    if name in _RELOCATED:
        module_path, target_name = _RELOCATED[name]
        warn_pending_change(
            f"railtracks.verifiers.{name}",
            change="moves",
            instead=f"{module_path}.{target_name}",
            detail="The behavior itself is unchanged.",
        )
        module = importlib.import_module(module_path)
        return getattr(module, target_name)

    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__() -> list[str]:
    return sorted([*__all__, *_RELOCATED])
