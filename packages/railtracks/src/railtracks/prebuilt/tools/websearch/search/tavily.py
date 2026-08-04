from __future__ import annotations

import os

import httpx

from ..models import SearchResult

_TAVILY_URL = "https://api.tavily.com/search"


class TavilySearch:
    """SearchBackend backed by the Tavily REST API.

    Talks to Tavily's single `/search` endpoint directly via httpx rather
    than depending on the `tavily-python` SDK, since httpx is already
    required by the default fetch backend.
    """

    def __init__(
        self, api_key: str | None = None, *, base_url: str = _TAVILY_URL
    ) -> None:
        self.api_key = api_key or os.getenv("TAVILY_API_KEY")
        if not self.api_key:
            raise ValueError(
                "Tavily API key not provided. Pass api_key=, or set the "
                "TAVILY_API_KEY environment variable."
            )
        self._base_url = base_url

    async def search(self, query: str, *, top_k: int = 5) -> list[SearchResult]:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                self._base_url,
                json={
                    "api_key": self.api_key,
                    "query": query,
                    "max_results": top_k,
                },
            )
            resp.raise_for_status()
            data = resp.json()

        return [
            SearchResult(
                title=result.get("title", ""),
                url=result.get("url", ""),
                snippet=result.get("content", ""),
            )
            for result in data.get("results", [])
        ]
