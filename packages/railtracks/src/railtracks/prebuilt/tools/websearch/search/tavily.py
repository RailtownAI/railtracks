from __future__ import annotations

import os

from tavily import AsyncTavilyClient

from ..models import SearchResult


class TavilySearch:
    """SearchBackend backed by the official `tavily-python` SDK.

    Uses `AsyncTavilyClient` rather than talking to Tavily's REST API
    directly, so if Tavily changes their API, keeping up with that is
    their SDK's job to maintain, not ours to track and patch.
    """

    def __init__(
        self, api_key: str | None = None, *, base_url: str | None = None
    ) -> None:
        """Create a Tavily-backed search backend.

        Args:
            api_key: Tavily API key. Falls back to the TAVILY_API_KEY
                environment variable if not provided; raises if neither is
                set.
            base_url: Override the Tavily API base URL, e.g. to point at a
                proxy or a mocked server in tests. Defaults to the SDK's own
                default when not set.
        """
        self.api_key = api_key or os.getenv("TAVILY_API_KEY")
        if not self.api_key:
            raise ValueError(
                "Tavily API key not provided. Pass api_key=, or set the "
                "TAVILY_API_KEY environment variable."
            )
        self._client = AsyncTavilyClient(api_key=self.api_key, api_base_url=base_url)

    async def search(self, query: str, *, top_k: int = 5) -> list[SearchResult]:
        response = await self._client.search(query, max_results=top_k)
        return [
            SearchResult(
                title=result.get("title", ""),
                url=result.get("url", ""),
                snippet=result.get("content", ""),
            )
            for result in response.get("results", [])
        ]
