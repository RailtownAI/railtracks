from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from railtracks.prebuilt.tools.websearch.search import SearchBackend
from railtracks.prebuilt.tools.websearch.search.tavily import TavilySearch


def _mock_client(json_payload=None, raise_status_error=False):
    """Build a fake httpx.AsyncClient context manager for `async with ... as client`."""
    response = MagicMock()
    if raise_status_error:
        response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "boom", request=MagicMock(), response=MagicMock()
        )
    else:
        response.raise_for_status.return_value = None
        response.json.return_value = json_payload or {}

    client = MagicMock()
    client.post = AsyncMock(return_value=response)

    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=client)
    cm.__aexit__ = AsyncMock(return_value=False)
    return cm


# ---------------------------------------------------------------------------
# API key handling
# ---------------------------------------------------------------------------


def test_missing_api_key_raises(monkeypatch):
    monkeypatch.delenv("TAVILY_API_KEY", raising=False)
    with pytest.raises(ValueError, match="TAVILY_API_KEY"):
        TavilySearch()


def test_explicit_api_key_used(monkeypatch):
    monkeypatch.delenv("TAVILY_API_KEY", raising=False)
    ts = TavilySearch(api_key="explicit-key")
    assert ts.api_key == "explicit-key"


def test_env_api_key_used(monkeypatch):
    monkeypatch.setenv("TAVILY_API_KEY", "env-key")
    ts = TavilySearch()
    assert ts.api_key == "env-key"


# ---------------------------------------------------------------------------
# search()
# ---------------------------------------------------------------------------


def test_satisfies_search_backend_protocol():
    assert isinstance(TavilySearch(api_key="x"), SearchBackend)


async def test_search_maps_results_in_order():
    payload = {
        "results": [
            {"title": "A", "url": "https://a.com", "content": "snippet a"},
            {"title": "B", "url": "https://b.com", "content": "snippet b"},
        ]
    }
    with patch("httpx.AsyncClient", return_value=_mock_client(payload)):
        results = await TavilySearch(api_key="x").search("query", top_k=2)

    assert [r.title for r in results] == ["A", "B"]
    assert results[0].url == "https://a.com"
    assert results[0].snippet == "snippet a"


async def test_search_missing_fields_default_to_empty():
    payload = {"results": [{"title": "A"}]}
    with patch("httpx.AsyncClient", return_value=_mock_client(payload)):
        results = await TavilySearch(api_key="x").search("query")

    assert results[0].url == ""
    assert results[0].snippet == ""


async def test_search_empty_results():
    with patch("httpx.AsyncClient", return_value=_mock_client({"results": []})):
        results = await TavilySearch(api_key="x").search("query")

    assert results == []


async def test_search_http_error_propagates():
    with patch("httpx.AsyncClient", return_value=_mock_client(raise_status_error=True)):
        with pytest.raises(httpx.HTTPStatusError):
            await TavilySearch(api_key="x").search("query")
