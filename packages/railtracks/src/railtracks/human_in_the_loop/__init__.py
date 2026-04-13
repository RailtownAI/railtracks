from __future__ import annotations

from .human_in_the_loop import HIL, HILMessage

__all__ = ["HIL", "HILMessage", "ChatUI"]


def __getattr__(name: str):
    if name == "ChatUI":
        try:
            from .local_chat_ui import ChatUI

            return ChatUI
        except ImportError as e:
            from railtracks.visual_extra import VisualExtraRequiredError

            raise VisualExtraRequiredError(
                "The local chat UI requires optional dependencies. "
                "Install with: pip install 'railtracks[visual]' "
                "(or 'railtracks[cli]' for backward compatibility)."
            ) from e
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__() -> list[str]:
    return sorted(set(__all__))
