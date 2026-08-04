"""Fetch backends for the prebuilt web search tools.

``FetchBackend`` is pure stdlib (a Protocol) and imported eagerly.
``HttpFetch`` requires the `websearch` extra (httpx, trafilatura), so it is
loaded lazily on first access — importing this package stays
dependency-light.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from .protocol import FetchBackend

if TYPE_CHECKING:
    from .http import HttpFetch

__all__ = [
    "FetchBackend",
    "HttpFetch",
]


def __getattr__(name: str):
    if name == "HttpFetch":
        from .http import HttpFetch

        return HttpFetch
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
