from __future__ import annotations

from pydantic import BaseModel


class SearchResult(BaseModel):
    """A single ranked web search result."""

    title: str
    url: str
    snippet: str


class FetchResult(BaseModel):
    """The outcome of fetching a URL and extracting its page content.

    A failed fetch (paywalled, blocked, no extractable content, network
    error) is represented by ``is_error=True`` with ``error_message`` set,
    rather than raising, these are expected, common outcomes for a fetch
    layer, not exceptional ones.
    """

    url: str
    title: str | None = None
    text: str = ""
    is_error: bool = False
    error_message: str | None = None
