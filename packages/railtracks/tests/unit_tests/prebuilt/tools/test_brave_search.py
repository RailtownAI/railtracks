"""Tests for prebuilt/tools/websearch/search/brave.py — BraveSearch."""

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from railtracks.prebuilt.tools.websearch.search import SearchBackend
from railtracks.prebuilt.tools.websearch.search.brave import BraveSearch


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
    client.get = AsyncMock(return_value=response)

    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=client)
    cm.__aexit__ = AsyncMock(return_value=False)
    return cm


# ---------------------------------------------------------------------------
# API key handling
# ---------------------------------------------------------------------------


def test_missing_api_key_raises(monkeypatch):
    monkeypatch.delenv("BRAVE_API_KEY", raising=False)
    with pytest.raises(ValueError, match="BRAVE_API_KEY"):
        BraveSearch()


def test_explicit_api_key_used(monkeypatch):
    monkeypatch.delenv("BRAVE_API_KEY", raising=False)
    bs = BraveSearch(api_key="explicit-key")
    assert bs.api_key == "explicit-key"


def test_env_api_key_used(monkeypatch):
    monkeypatch.setenv("BRAVE_API_KEY", "env-key")
    bs = BraveSearch()
    assert bs.api_key == "env-key"


# ---------------------------------------------------------------------------
# search()
# ---------------------------------------------------------------------------


def test_satisfies_search_backend_protocol():
    assert isinstance(BraveSearch(api_key="x"), SearchBackend)


async def test_search_maps_results_in_order():
    payload = {
        "web": {
            "results": [
                {"title": "A", "url": "https://a.com", "description": "snippet a"},
                {"title": "B", "url": "https://b.com", "description": "snippet b"},
            ]
        }
    }
    with patch("httpx.AsyncClient", return_value=_mock_client(payload)):
        results = await BraveSearch(api_key="x").search("query", top_k=2)

    assert [r.title for r in results] == ["A", "B"]
    assert results[0].url == "https://a.com"
    assert results[0].snippet == "snippet a"


async def test_search_missing_fields_default_to_empty():
    payload = {"web": {"results": [{"title": "A"}]}}
    with patch("httpx.AsyncClient", return_value=_mock_client(payload)):
        results = await BraveSearch(api_key="x").search("query")

    assert results[0].url == ""
    assert results[0].snippet == ""


async def test_search_empty_results():
    with patch(
        "httpx.AsyncClient", return_value=_mock_client({"web": {"results": []}})
    ):
        results = await BraveSearch(api_key="x").search("query")

    assert results == []


async def test_search_missing_web_key_returns_empty():
    with patch("httpx.AsyncClient", return_value=_mock_client({})):
        results = await BraveSearch(api_key="x").search("query")

    assert results == []


async def test_search_http_error_propagates():
    with patch("httpx.AsyncClient", return_value=_mock_client(raise_status_error=True)):
        with pytest.raises(httpx.HTTPStatusError):
            await BraveSearch(api_key="x").search("query")
