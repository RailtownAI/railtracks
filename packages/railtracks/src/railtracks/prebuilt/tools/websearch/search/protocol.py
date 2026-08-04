from __future__ import annotations

from typing import Protocol, runtime_checkable

from ..models import SearchResult


@runtime_checkable
class SearchBackend(Protocol):
    """Runs a web search and returns ranked results.

    Callers (e.g. ``WebSearchToolSet``) depend on this protocol rather than a
    concrete search provider, so the backend can be swapped — Tavily, Brave,
    SerpAPI, or any other implementation — without touching the toolset.
    """

    async def search(self, query: str, *, top_k: int = 5) -> list[SearchResult]:
        """Return up to ``top_k`` search results, best first.

        Args:
            query: Free-text search query.
            top_k: Maximum number of results to return.

        Raises:
            Exception: Implementations may raise on backend/network failure;
                callers are responsible for catching and degrading gracefully.
        """
        ...
