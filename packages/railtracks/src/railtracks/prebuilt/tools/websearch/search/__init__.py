"""Search backends for the prebuilt web search tools.

``SearchBackend`` is pure stdlib (a Protocol) and imported eagerly.
``TavilySearch`` requires the `websearch` extra (httpx), so it is loaded
lazily on first access — importing this package stays dependency-light.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from .protocol import SearchBackend

if TYPE_CHECKING:
    from .tavily import TavilySearch

__all__ = [
    "SearchBackend",
    "TavilySearch",
]


def __getattr__(name: str):
    if name == "TavilySearch":
        from .tavily import TavilySearch

        return TavilySearch
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
