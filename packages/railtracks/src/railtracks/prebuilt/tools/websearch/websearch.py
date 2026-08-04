from __future__ import annotations

from typing import TYPE_CHECKING

import railtracks as rt
from railtracks.built_nodes.concrete.function_base import RTFunction
from railtracks.utils.logging.create import get_rt_logger

from .._base import ToolSet

if TYPE_CHECKING:
    from .fetch import FetchBackend
    from .search import SearchBackend

logger = get_rt_logger(__name__)


def _default_search() -> SearchBackend:
    from .search import TavilySearch

    return TavilySearch()


def _default_fetch() -> FetchBackend:
    from .fetch import HttpFetch

    return HttpFetch()


class WebSearchToolSet(ToolSet):
    """Prebuilt web search + page-fetch tools for an agent.

    Gives an agent the ability to search the live web and read full page
    content: ``search()`` for ranked title/url/snippet results, ``fetch()``
    to read one result's full content, and ``search_and_fetch()`` to do both
    in a single call. Defaults to Tavily for search and an httpx + trafilatura
    HTML-to-text extractor for fetch; both are swappable via constructor
    injection::

        toolset = WebSearchToolSet(search=MySearchBackend(), fetch=MyFetchBackend())

    Backend/network failures are caught and returned as a descriptive string
    rather than raised, so a backend outage never breaks the agent's turn;
    semantic fetch failures (paywalled, blocked, no extractable content) are
    likewise reported as text rather than an exception.

    Args:
        search: Backend used by search()/search_and_fetch(). Defaults to
            ``TavilySearch()`` (requires a ``TAVILY_API_KEY``).
        fetch: Backend used by fetch()/search_and_fetch(). Defaults to
            ``HttpFetch()``.
    """

    def __init__(
        self,
        search: SearchBackend | None = None,
        fetch: FetchBackend | None = None,
    ) -> None:
        self.search_backend: SearchBackend = (
            search if search is not None else _default_search()
        )
        self.fetch_backend: FetchBackend = (
            fetch if fetch is not None else _default_fetch()
        )

    async def search(self, query: str, top_k: int = 5) -> str:
        """Search the web and return ranked results (title, URL, snippet).

        Use this to find candidate pages before fetching full content with
        fetch(), or use search_and_fetch() to do both in one call.

        Args:
            query: Free-text search query.
            top_k: Maximum number of results to return.

        Returns:
            Newline-separated "title — url" entries with a snippet on each,
            ranked by relevance, or a message saying the search failed or
            found nothing.
        """
        try:
            results = await self.search_backend.search(query, top_k=top_k)
        except Exception as e:
            logger.error(f"WebSearch search backend error for query {query!r}: {e}")
            return f"Search failed: {e}"

        if not results:
            return f"No results found for '{query}'."
        return "\n".join(f"- {r.title} — {r.url}\n  {r.snippet}" for r in results)

    async def fetch(self, url: str) -> str:
        """Fetch a URL (typically from search() results) and return cleaned page text.

        Args:
            url: The page URL to retrieve. Should be an http(s) URL, usually
                one returned by search().

        Returns:
            The extracted, human-readable text content of the page, or a
            message describing why the fetch failed (blocked, paywalled,
            not found, no extractable content) so a different result can be
            tried instead.
        """
        try:
            result = await self.fetch_backend.fetch(url)
        except Exception as e:
            logger.error(f"WebSearch fetch backend error for url {url!r}: {e}")
            return f"Fetch failed for '{url}': {e}"

        if result.is_error:
            return f"Fetch failed for '{url}': {result.error_message}"

        header = f"{result.title}\n" if result.title else ""
        return f"{header}{result.text}"

    async def search_and_fetch(self, query: str, top_k: int = 3) -> str:
        """Search the web and fetch full content for each top result in one call.

        Convenience wrapper combining search() and fetch(); use when you want
        full page content immediately without an extra round trip, at the
        cost of fetching (and paying token cost for) top_k pages instead of
        one. Individual fetch failures are reported inline rather than
        aborting the whole call.

        Args:
            query: Free-text search query.
            top_k: Number of top results to fetch full content for.

        Returns:
            For each result: title, url, and either its cleaned text or an
            inline error message, separated by section dividers.
        """
        try:
            results = await self.search_backend.search(query, top_k=top_k)
        except Exception as e:
            logger.error(f"WebSearch search backend error for query {query!r}: {e}")
            return f"Search failed: {e}"

        if not results:
            return f"No results found for '{query}'."

        sections = []
        for r in results:
            try:
                fetched = await self.fetch_backend.fetch(r.url)
                body = (
                    fetched.text
                    if not fetched.is_error
                    else f"[fetch failed: {fetched.error_message}]"
                )
            except Exception as e:
                logger.error(f"WebSearch fetch backend error for url {r.url!r}: {e}")
                body = f"[fetch failed: {e}]"
            sections.append(f"## {r.title}\n{r.url}\n\n{body}")
        return "\n\n---\n\n".join(sections)

    @classmethod
    def prompt(cls) -> str:
        return (
            "Use the web search tools to find and read current information from the "
            "live web. Call search(query) to get ranked title/url/snippet results, "
            "then fetch(url) on the most promising result(s) to read full page content. "
            "Use search_and_fetch(query) when you want full content for the top results "
            "in a single step. If a fetch fails (blocked, paywalled, no content), try "
            "another result instead of retrying the same URL."
        )

    def tool_set(self) -> list[RTFunction]:
        functions = [self.search, self.fetch, self.search_and_fetch]
        return [rt.function_node(func) for func in functions]
