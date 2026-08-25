from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

pytest.importorskip("trafilatura")

from railtracks.prebuilt.tools.websearch.fetch import FetchBackend  # noqa: E402
from railtracks.prebuilt.tools.websearch.fetch.http import HttpFetch  # noqa: E402

_SAMPLE_HTML = """
<html><head><title>Sample Page</title></head>
<body>
<nav>Home | About | Contact</nav>
<article><p>This is the real body content worth extracting.</p></article>
<footer>Copyright 2026</footer>
</body></html>
"""


def _mock_client(text=_SAMPLE_HTML, raise_error=None):
    response = MagicMock()
    response.text = text
    if raise_error is not None:
        response.raise_for_status.side_effect = raise_error
    else:
        response.raise_for_status.return_value = None

    client = MagicMock()
    client.get = AsyncMock(return_value=response)

    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=client)
    cm.__aexit__ = AsyncMock(return_value=False)
    return cm


def test_satisfies_fetch_backend_protocol():
    assert isinstance(HttpFetch(), FetchBackend)


async def test_fetch_extracts_clean_text():
    with patch("httpx.AsyncClient", return_value=_mock_client()):
        result = await HttpFetch().fetch("https://example.com")

    assert result.is_error is False
    assert result.title == "Sample Page"
    assert "real body content" in result.text


async def test_fetch_http_error_is_not_raised():
    error = httpx.HTTPStatusError("404", request=MagicMock(), response=MagicMock())
    with patch("httpx.AsyncClient", return_value=_mock_client(raise_error=error)):
        result = await HttpFetch().fetch("https://example.com/missing")

    assert result.is_error is True
    assert "Fetch failed" in result.error_message


async def test_fetch_timeout_is_not_raised():
    error = httpx.TimeoutException("timed out")
    with patch("httpx.AsyncClient", return_value=_mock_client(raise_error=error)):
        result = await HttpFetch().fetch("https://example.com/slow")

    assert result.is_error is True
    assert "Fetch failed" in result.error_message


async def test_fetch_empty_extraction_reports_error():
    with patch("httpx.AsyncClient", return_value=_mock_client(text="<html></html>")):
        result = await HttpFetch().fetch("https://example.com/blank")

    assert result.is_error is True
    assert "no extractable content" in result.error_message
