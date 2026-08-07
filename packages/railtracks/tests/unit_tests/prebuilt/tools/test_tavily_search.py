"""Tests for prebuilt/tools/websearch/search/tavily.py — TavilySearch."""

from unittest.mock import AsyncMock, patch

import pytest
from railtracks.prebuilt.tools.websearch.search import SearchBackend
from railtracks.prebuilt.tools.websearch.search.tavily import TavilySearch
from tavily import BadRequestError

_PATCH_TARGET = "railtracks.prebuilt.tools.websearch.search.tavily.AsyncTavilyClient"


def _mock_sdk_client(response=None, raise_error=None):
    """Build a fake AsyncTavilyClient whose .search() returns/raises as configured."""
    client = AsyncMock()
    if raise_error is not None:
        client.search.side_effect = raise_error
    else:
        client.search.return_value = response or {}
    return client


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
    with patch(_PATCH_TARGET, return_value=_mock_sdk_client(payload)):
        results = await TavilySearch(api_key="x").search("query", top_k=2)

    assert [r.title for r in results] == ["A", "B"]
    assert results[0].url == "https://a.com"
    assert results[0].snippet == "snippet a"


async def test_search_missing_fields_default_to_empty():
    payload = {"results": [{"title": "A"}]}
    with patch(_PATCH_TARGET, return_value=_mock_sdk_client(payload)):
        results = await TavilySearch(api_key="x").search("query")

    assert results[0].url == ""
    assert results[0].snippet == ""


async def test_search_empty_results():
    with patch(_PATCH_TARGET, return_value=_mock_sdk_client({"results": []})):
        results = await TavilySearch(api_key="x").search("query")

    assert results == []


async def test_search_sdk_error_propagates():
    with patch(
        _PATCH_TARGET,
        return_value=_mock_sdk_client(raise_error=BadRequestError("bad query")),
    ):
        with pytest.raises(BadRequestError):
            await TavilySearch(api_key="x").search("query")


async def test_search_passes_max_results():
    client = _mock_sdk_client({"results": []})
    with patch(_PATCH_TARGET, return_value=client):
        await TavilySearch(api_key="x").search("query", top_k=7)

    client.search.assert_awaited_once_with("query", max_results=7)
