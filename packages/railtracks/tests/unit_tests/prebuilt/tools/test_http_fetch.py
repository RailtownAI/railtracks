import gzip

import httpx
import pytest

pytest.importorskip("trafilatura")

from railtracks.llm._url_fetch import BlockedURLError, FetchResponse  # noqa: E402
from railtracks.prebuilt.tools.websearch.fetch import FetchBackend  # noqa: E402
from railtracks.prebuilt.tools.websearch.fetch import http as http_module  # noqa: E402
from railtracks.prebuilt.tools.websearch.fetch.http import HttpFetch  # noqa: E402

_SAMPLE_HTML = b"""
<html><head><title>Sample Page</title></head>
<body>
<nav>Home | About | Contact</nav>
<article><p>This is the real body content worth extracting.</p></article>
<footer>Copyright 2026</footer>
</body></html>
"""


@pytest.fixture
def fetched(monkeypatch: pytest.MonkeyPatch) -> list[dict[str, object]]:
    """Replace the guarded fetch with one that serves `_SAMPLE_HTML`, recording each call."""
    calls: list[dict[str, object]] = []

    def fake_fetch(url: str, **kwargs: object) -> FetchResponse:
        calls.append({"url": url, **kwargs})
        return FetchResponse(url=url, headers=httpx.Headers(), body=_SAMPLE_HTML)

    monkeypatch.setattr(http_module, "guarded_fetch", fake_fetch)
    return calls


def _failing_fetch(error: Exception):
    def fake_fetch(url: str, **kwargs: object) -> FetchResponse:
        raise error

    return fake_fetch


def test_satisfies_fetch_backend_protocol():
    assert isinstance(HttpFetch(), FetchBackend)


async def test_fetch_extracts_clean_text(fetched):
    result = await HttpFetch().fetch("https://example.com")

    assert result.is_error is False
    assert result.title == "Sample Page"
    assert "real body content" in (result.text or "")


async def test_settings_reach_the_guarded_fetch(fetched):
    await HttpFetch(timeout=3.0, user_agent="agent/2.0", max_mb=4.0).fetch(
        "https://example.com"
    )

    assert fetched == [
        {
            "url": "https://example.com",
            "timeout": 3.0,
            "max_mb": 4.0,
            "user_agent": "agent/2.0",
        }
    ]


@pytest.mark.parametrize(
    "error",
    [
        ValueError("HTTP 404 from https://example.com/missing."),
        OSError("Could not fetch https://example.com/slow: ReadTimeout('timed out')"),
        BlockedURLError("Refused to fetch http://internal/: non-public address."),
    ],
)
async def test_fetch_failure_is_not_raised(monkeypatch, error):
    monkeypatch.setattr(http_module, "guarded_fetch", _failing_fetch(error))

    result = await HttpFetch().fetch("https://example.com/page")

    assert result.is_error is True
    assert "Fetch failed" in (result.error_message or "")


async def test_internal_address_is_refused_before_connecting(monkeypatch):
    def boom_send(transport, request):
        raise AssertionError(f"must not send {request!r}")

    monkeypatch.setattr(httpx.HTTPTransport, "handle_request", boom_send)

    result = await HttpFetch().fetch("http://169.254.169.254/latest/meta-data/")

    assert result.is_error is True
    assert "non-public address" in (result.error_message or "")


async def test_fetch_empty_extraction_reports_error(monkeypatch):
    def empty_fetch(url: str, **kwargs: object) -> FetchResponse:
        return FetchResponse(url=url, headers=httpx.Headers(), body=b"<html></html>")

    monkeypatch.setattr(http_module, "guarded_fetch", empty_fetch)

    result = await HttpFetch().fetch("https://example.com/blank")

    assert result.is_error is True
    assert "no extractable content" in (result.error_message or "")


async def test_compressed_page_is_not_inflated(monkeypatch):
    """The size cap counts bytes as sent, so the extractor must not decompress them either."""

    def gzip_fetch(url: str, **kwargs: object) -> FetchResponse:
        headers = httpx.Headers({"Content-Encoding": "gzip"})
        return FetchResponse(url=url, headers=headers, body=gzip.compress(_SAMPLE_HTML))

    monkeypatch.setattr(http_module, "guarded_fetch", gzip_fetch)

    result = await HttpFetch().fetch("https://example.com/gzip")

    assert result.is_error is True
    assert "no extractable content" in (result.error_message or "")


@pytest.mark.parametrize("max_mb", [0, -1, float("inf"), float("nan")])
def test_max_mb_must_be_positive_and_finite(max_mb):
    with pytest.raises(ValueError, match="max_mb must be a positive, finite number"):
        HttpFetch(max_mb=max_mb)
