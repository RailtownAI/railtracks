import socket
import threading
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import litellm
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
_PUBLIC_IP = "93.184.215.14"
_METADATA_URL = "http://169.254.169.254/latest/meta-data/"
_REDIRECTS = {"/to-metadata": _METADATA_URL, "/moved": "/"}


@pytest.fixture(autouse=True)
def public_dns(monkeypatch):
    """Resolve example.com to a public address so no test needs the network."""
    real_getaddrinfo = socket.getaddrinfo

    def fake_getaddrinfo(host, port, *args, **kwargs):
        if host == "example.com":
            return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (_PUBLIC_IP, port))]
        return real_getaddrinfo(host, port, *args, **kwargs)

    monkeypatch.setattr(socket, "getaddrinfo", fake_getaddrinfo)


def _mock_client(text=_SAMPLE_HTML, raise_error=None):
    response = MagicMock()
    response.text = text
    response.is_redirect = False
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


class _PageHandler(BaseHTTPRequestHandler):
    """Serves `_SAMPLE_HTML`, or a redirect for the paths in `_REDIRECTS`."""

    paths: list[str] = []

    def do_GET(self) -> None:
        self.paths.append(self.path)
        if self.path in _REDIRECTS:
            self.send_response(302)
            self.send_header("Location", _REDIRECTS[self.path])
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        body = _SAMPLE_HTML.encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: object) -> None:
        pass


@pytest.fixture
def local_server() -> Iterator[str]:
    _PageHandler.paths = []
    server = ThreadingHTTPServer(("127.0.0.1", 0), _PageHandler)
    thread = threading.Thread(
        target=server.serve_forever, kwargs={"poll_interval": 0.01}
    )
    thread.start()
    try:
        yield f"127.0.0.1:{server.server_address[1]}"
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


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
    assert "Fetch failed" in (result.error_message or "")


async def test_fetch_timeout_is_not_raised():
    error = httpx.TimeoutException("timed out")
    with patch("httpx.AsyncClient", return_value=_mock_client(raise_error=error)):
        result = await HttpFetch().fetch("https://example.com/slow")

    assert result.is_error is True
    assert "Fetch failed" in (result.error_message or "")


async def test_fetch_empty_extraction_reports_error():
    with patch("httpx.AsyncClient", return_value=_mock_client(text="<html></html>")):
        result = await HttpFetch().fetch("https://example.com/blank")

    assert result.is_error is True
    assert "no extractable content" in (result.error_message or "")


# The tests below run litellm's address check for real, so a litellm upgrade
# that changes or removes it fails here.


async def test_fetch_refuses_loopback(local_server):
    result = await HttpFetch().fetch(f"http://{local_server}/")

    assert result.is_error is True
    assert "blocked address" in (result.error_message or "")
    assert _PageHandler.paths == []


async def test_fetch_refuses_the_metadata_service():
    result = await HttpFetch().fetch(_METADATA_URL)

    assert result.is_error is True
    assert "blocked address" in (result.error_message or "")


async def test_fetch_allows_hosts_listed_in_litellm(local_server, monkeypatch):
    monkeypatch.setattr(litellm, "user_url_allowed_hosts", [local_server])

    result = await HttpFetch().fetch(f"http://{local_server}/")

    assert result.is_error is False
    assert "real body content" in result.text


async def test_fetch_checks_every_redirect(local_server, monkeypatch):
    monkeypatch.setattr(litellm, "user_url_allowed_hosts", [local_server])

    result = await HttpFetch().fetch(f"http://{local_server}/to-metadata")

    assert result.is_error is True
    assert "blocked address" in (result.error_message or "")
    assert _PageHandler.paths == ["/to-metadata"]


async def test_fetch_follows_a_relative_redirect(local_server, monkeypatch):
    monkeypatch.setattr(litellm, "user_url_allowed_hosts", [local_server])

    result = await HttpFetch().fetch(f"http://{local_server}/moved")

    assert result.is_error is False
    assert _PageHandler.paths == ["/moved", "/"]


@pytest.mark.parametrize("ssl_verify,expected", [(True, True), (False, False)])
async def test_fetch_matches_litellm_ssl_verify(monkeypatch, ssl_verify, expected):
    monkeypatch.setattr(litellm, "ssl_verify", ssl_verify)
    with patch("httpx.AsyncClient", return_value=_mock_client()) as client_cls:
        await HttpFetch().fetch("https://example.com")

    assert client_cls.call_args.kwargs["verify"] is expected


async def test_fetch_malformed_port_is_not_raised():
    result = await HttpFetch().fetch("http://example.com:99999/")

    assert result.is_error is True
    assert "Fetch failed" in (result.error_message or "")
