"""Search backends for the prebuilt web search tools.

``SearchBackend`` is pure stdlib (a Protocol) and imported eagerly.
``TavilySearch``/``BraveSearch`` require the `websearch` extra (httpx), so
they are loaded lazily on first access; importing this package for the
protocol alone stays dependency-light.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from .protocol import SearchBackend

if TYPE_CHECKING:
    from .brave import BraveSearch
    from .tavily import TavilySearch

__all__ = [
    "BraveSearch",
    "SearchBackend",
    "TavilySearch",
]


def __getattr__(name: str):
    if name == "TavilySearch":
        from .tavily import TavilySearch

        return TavilySearch
    if name == "BraveSearch":
        from .brave import BraveSearch

        return BraveSearch
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
