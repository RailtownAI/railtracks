from __future__ import annotations

from abc import abstractmethod
from typing import Protocol, runtime_checkable

from ..models import FetchResult


@runtime_checkable
class FetchBackend(Protocol):
    """Retrieves a URL and returns cleaned page content.

    Callers (e.g. ``WebSearchToolSet``) depend on this protocol rather than a
    concrete fetch implementation, so the backend can be swapped, a plain
    HTTP + HTML-to-text extractor today, a headless browser for JS-heavy
    pages later, without touching the toolset.
    """

    @abstractmethod
    async def fetch(self, url: str) -> FetchResult:
        """Fetch ``url`` and return its cleaned text content.

        Expected failure modes (blocked, paywalled, no extractable content,
        network error) are represented via ``FetchResult(is_error=True, ...)``
        rather than a raised exception, these are common outcomes for a
        fetch layer, not exceptional ones.
        """
        pass
