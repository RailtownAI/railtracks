from __future__ import annotations

import os

import httpx

from ..models import SearchResult

_BRAVE_URL = "https://api.search.brave.com/res/v1/web/search"


class BraveSearch:
    """SearchBackend backed by the Brave Search API.

    Talks to Brave's `/web/search` endpoint directly via httpx rather than
    depending on a separate SDK, matching TavilySearch's approach.
    """

    def __init__(
        self, api_key: str | None = None, *, base_url: str = _BRAVE_URL
    ) -> None:
        """Create a Brave-backed search backend.

        Args:
            api_key: Brave Search API key (a "subscription token"). Falls
                back to the BRAVE_API_KEY environment variable if not
                provided; raises if neither is set.
            base_url: Override the Brave search endpoint, e.g. to point at
                a proxy or a mocked server in tests.
        """
        self.api_key = api_key or os.getenv("BRAVE_API_KEY")
        if not self.api_key:
            raise ValueError(
                "Brave API key not provided. Pass api_key=, or set the "
                "BRAVE_API_KEY environment variable."
            )
        self._base_url = base_url

    async def search(self, query: str, *, top_k: int = 5) -> list[SearchResult]:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                self._base_url,
                params={"q": query, "count": top_k},
                headers={
                    "Accept": "application/json",
                    "X-Subscription-Token": self.api_key,
                },
            )
            resp.raise_for_status()
            data = resp.json()

        results = data.get("web", {}).get("results", [])
        return [
            SearchResult(
                title=result.get("title", ""),
                url=result.get("url", ""),
                snippet=result.get("description", ""),
            )
            for result in results
        ]
