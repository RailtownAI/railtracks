import http.client
import socket
import ssl
import threading
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import cast
from unittest.mock import Mock
from urllib.parse import quote, unquote

import pytest
from railtracks.llm import _url_fetch
from railtracks.llm._url_fetch import (
    MAX_REDIRECTS,
    BlockedURLError,
    _PinnedHTTPSConnection,
    fetch,
    is_blocked_address,
    read_capped,
    redact_url,
)

_BODY = b"hello"
_LARGE_BODY = b"x" * 2000
_TINY_MB = 1000 / (1024 * 1024)  # 1000 bytes


class _Server(ThreadingHTTPServer):
    requests: list[tuple[str, str, str | None]]


class _Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        self._respond(send_body=True)

    def do_HEAD(self) -> None:
        self._respond(send_body=False)

    def log_message(self, format: str, *args: object) -> None:
        pass

    def _respond(self, *, send_body: bool) -> None:
        cast(_Server, self.server).requests.append(
            (self.command, self.path, self.headers.get("Host"))
        )
        path, _, query = self.path.partition("?")
        if path == "/redirect":
            self._redirect(unquote(query.removeprefix("to=")))
        elif path == "/relative":
            self._redirect("/ok")
        elif path == "/loop":
            self._redirect("/loop")
        elif path == "/no-location":
            self.send_response(302)
            self.end_headers()
        elif path == "/missing":
            self.send_response(404)
            self.send_header("Content-Length", "0")
            self.end_headers()
        elif path == "/garbage":
            self.wfile.write(b"garbage\r\n\r\n")
        elif path == "/large":
            self._ok(_LARGE_BODY, send_body=send_body)
        elif path == "/stream":
            # HTTP/1.0 without Content-Length: the body ends when the connection closes.
            self.send_response(200)
            self.end_headers()
            if send_body:
                self.wfile.write(_LARGE_BODY)
        else:
            self._ok(_BODY, send_body=send_body)

    def _ok(self, body: bytes, *, send_body: bool) -> None:
        self.send_response(200)
        self.send_header("Content-Type", "application/pdf")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        if send_body:
            self.wfile.write(body)

    def _redirect(self, location: str) -> None:
        self.send_response(302)
        self.send_header("Location", location)
        self.send_header("Content-Length", "0")
        self.end_headers()


@pytest.fixture
def server() -> Iterator[_Server]:
    httpd = _Server(("127.0.0.1", 0), _Handler)
    httpd.requests = []
    thread = threading.Thread(
        target=httpd.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True
    )
    thread.start()
    yield httpd
    httpd.shutdown()
    httpd.server_close()


@pytest.fixture
def resolver(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Fake DNS where `public.test` is the local server, treated as a public address."""
    hosts = {
        "public.test": ["127.0.0.1"],
        "internal.test": ["10.0.0.1"],
        "mixed.test": ["127.0.0.1", "10.0.0.1"],
    }
    lookups: list[str] = []

    def fake_getaddrinfo(host, port, *args, **kwargs):
        lookups.append(host)
        if host not in hosts:
            raise socket.gaierror(f"unknown test host {host!r}")
        return [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", (ip, port))
            for ip in hosts[host]
        ]

    real_is_blocked = _url_fetch.is_blocked_address
    monkeypatch.setattr(
        _url_fetch,
        "is_blocked_address",
        lambda address: address != "127.0.0.1" and real_is_blocked(address),
    )
    monkeypatch.setattr(socket, "getaddrinfo", fake_getaddrinfo)
    return lookups


@pytest.fixture
def no_connect(monkeypatch: pytest.MonkeyPatch) -> None:
    def boom_connect(addresses, timeout):
        raise AssertionError(f"must not connect to {addresses!r}")

    monkeypatch.setattr(_url_fetch, "_connect", boom_connect)


def _url(server: _Server, path: str, host: str = "public.test") -> str:
    return f"http://{host}:{server.server_address[1]}{path}"


class TestIsBlockedAddress:
    @pytest.mark.parametrize(
        "address",
        [
            "10.0.0.1",
            "172.16.0.1",
            "192.168.1.1",
            "127.0.0.1",
            "0.0.0.0",
            "169.254.169.254",  # AWS, GCP and Azure metadata
            "100.100.100.200",  # Alibaba Cloud metadata, in CGNAT
            "192.0.0.192",  # legacy Oracle Cloud metadata
            "192.0.2.1",  # documentation
            "198.51.100.1",  # documentation
            "203.0.113.1",  # documentation
            "224.0.0.1",  # multicast
            "240.0.0.1",  # reserved
            "255.255.255.255",  # broadcast
            "168.63.129.16",  # Azure Wire Server
            "::1",
            "::",
            "fd00:ec2::254",  # AWS IPv6 metadata, in fc00::/7
            "fe80::1",
            "fe80::1%eth0",
            "fec0::1",  # deprecated site-local
            "ff02::1",  # multicast
            "::ffff:10.0.0.1",
            "::ffff:169.254.169.254",
            "::ffff:168.63.129.16",
            "64:ff9b::a9fe:a9fe",  # NAT64 of 169.254.169.254
            "2002:a9fe:a9fe::1",  # 6to4 of 169.254.169.254
            "::a9fe:a9fe",  # IPv4-compatible 169.254.169.254
            "::ffff:0:a9fe:a9fe",  # SIIT 169.254.169.254
            "64:ff9b:1::a9fe:a9fe",  # local-use NAT64
            "not-an-ip",
        ],
    )
    def test_blocks_non_public_addresses(self, address):
        assert is_blocked_address(address) is True

    @pytest.mark.parametrize(
        "address",
        ["8.8.8.8", "93.184.216.34", "2606:4700:4700::1111", "::ffff:8.8.8.8"],
    )
    def test_allows_public_addresses(self, address):
        assert is_blocked_address(address) is False


class TestRedactUrl:
    @pytest.mark.parametrize(
        "url,expected",
        [
            (
                "https://user:pw@example.com:8443/a/b.pdf?sig=secret#frag",
                "https://example.com:8443/a/b.pdf",
            ),
            ("http://[::1]/x?token=secret", "http://[::1]/x"),
            ("https://example.com", "https://example.com"),
            ("http://example.com:notaport/x", "<unparseable URL>"),
        ],
    )
    def test_drops_credentials_query_and_fragment(self, url, expected):
        assert redact_url(url) == expected


@pytest.mark.usefixtures("no_connect")
class TestRefusedBeforeConnecting:
    @pytest.mark.parametrize(
        "url",
        [
            "ftp://example.com/report.pdf",
            "ftps://example.com/report.pdf",
            "file:///etc/passwd",
            "gopher://example.com/",
            "data:application/pdf;base64,JVBERi0=",
            "http:///no-host",
        ],
    )
    def test_scheme_and_host_allowlist(self, url):
        with pytest.raises(BlockedURLError):
            fetch(url, timeout=1.0, max_mb=1.0)

    @pytest.mark.parametrize(
        "url",
        [
            "http://127.0.0.1/",
            "http://[::1]/",
            "http://169.254.169.254/latest/meta-data/",
            "http://10.0.1.5:8080/v1/completions",
            "http://172.16.0.1/",
            "http://192.168.1.1/",
            "http://0.0.0.0/",
            "http://[::ffff:169.254.169.254]/",
            "https://168.63.129.16/",
        ],
    )
    def test_ip_literals(self, url):
        with pytest.raises(BlockedURLError, match="non-public address"):
            fetch(url, timeout=1.0, max_mb=1.0)

    def test_localhost_hostname(self, monkeypatch):
        def fake_getaddrinfo(host, port, *args, **kwargs):
            return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", port))]

        monkeypatch.setattr(socket, "getaddrinfo", fake_getaddrinfo)
        with pytest.raises(BlockedURLError):
            fetch("http://localhost/", method="HEAD", timeout=1.0)

    def test_dns_failure_is_an_os_error(self, monkeypatch):
        def fake_getaddrinfo(host, port, *args, **kwargs):
            raise socket.gaierror("Name or service not known")

        monkeypatch.setattr(socket, "getaddrinfo", fake_getaddrinfo)
        with pytest.raises(OSError):
            fetch("http://does-not-exist.invalid/", timeout=1.0, max_mb=1.0)

    def test_get_requires_max_mb(self):
        with pytest.raises(ValueError, match="max_mb is required"):
            fetch("https://example.com/report.pdf", timeout=1.0)


@pytest.mark.usefixtures("resolver")
class TestFetch:
    def test_get_returns_body_and_headers(self, server):
        response = fetch(_url(server, "/report.pdf"), timeout=5.0, max_mb=1.0)

        assert response.body == _BODY
        assert response.headers["Content-Type"] == "application/pdf"
        port = server.server_address[1]
        assert server.requests == [("GET", "/report.pdf", f"public.test:{port}")]

    def test_head_skips_the_body(self, server):
        response = fetch(_url(server, "/report.pdf"), method="HEAD", timeout=5.0)

        assert response.body == b""
        assert server.requests[0][0] == "HEAD"

    def test_request_target_is_percent_encoded(self, server):
        fetch(_url(server, "/a b/é.pdf?q=x y"), timeout=5.0, max_mb=1.0)

        assert server.requests[0][1] == "/a%20b/%C3%A9.pdf?q=x%20y"

    def test_any_blocked_address_refuses_the_host(self, server):
        with pytest.raises(
            BlockedURLError, match=r"non-public address \(10\.0\.0\.1\)"
        ):
            fetch(_url(server, "/ok", host="mixed.test"), timeout=5.0, max_mb=1.0)
        assert server.requests == []

    def test_proxy_environment_is_ignored(self, server, monkeypatch):
        for name in ("HTTP_PROXY", "http_proxy", "HTTPS_PROXY", "https_proxy"):
            monkeypatch.setenv(name, "http://10.255.255.1:9")

        assert fetch(_url(server, "/ok"), timeout=5.0, max_mb=1.0).body == _BODY

    def test_non_2xx_status_raises_without_the_query(self, server):
        with pytest.raises(ValueError, match="HTTP 404") as excinfo:
            fetch(_url(server, "/missing?sig=secret"), timeout=5.0, max_mb=1.0)
        assert "secret" not in str(excinfo.value)

    def test_malformed_response_is_a_value_error(self, server):
        with pytest.raises(ValueError, match="Bad HTTP response") as excinfo:
            fetch(_url(server, "/garbage?sig=secret"), timeout=5.0, max_mb=1.0)
        assert "secret" not in str(excinfo.value)

    def test_https_context_verifies_certificates(self, monkeypatch):
        contexts: list[ssl.SSLContext] = []

        def capture_connect(conn: _PinnedHTTPSConnection) -> None:
            contexts.append(conn._tls_context)
            raise OSError("stop before the network")

        monkeypatch.setattr(_PinnedHTTPSConnection, "connect", capture_connect)
        with pytest.raises(OSError, match="stop before the network"):
            fetch("https://public.test/report.pdf", timeout=5.0, max_mb=1.0)

        assert contexts[0].verify_mode == ssl.CERT_REQUIRED
        assert contexts[0].check_hostname is True


class TestDnsRebinding:
    def test_connects_to_the_checked_address(self, server, monkeypatch):
        """A second DNS answer pointing at a private address is never used."""
        lookups: list[str] = []

        def rebinding_getaddrinfo(host, port, *args, **kwargs):
            lookups.append(host)
            ip = "127.0.0.1" if len(lookups) == 1 else "10.0.0.1"
            return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (ip, port))]

        real_is_blocked = _url_fetch.is_blocked_address
        monkeypatch.setattr(
            _url_fetch,
            "is_blocked_address",
            lambda address: address != "127.0.0.1" and real_is_blocked(address),
        )
        monkeypatch.setattr(socket, "getaddrinfo", rebinding_getaddrinfo)

        response = fetch(
            _url(server, "/ok", host="rebind.test"), timeout=5.0, max_mb=1.0
        )

        assert response.body == _BODY
        assert lookups == ["rebind.test"]

    def test_https_verifies_the_hostname_on_the_pinned_socket(self, monkeypatch):
        pinned = object()
        addresses = [(socket.AF_INET, ("93.184.216.34", 443))]
        connected_to = []

        def fake_connect(addrs, timeout):
            connected_to.append(addrs)
            return pinned

        monkeypatch.setattr(_url_fetch, "_connect", fake_connect)
        context = Mock()
        conn = _PinnedHTTPSConnection(
            "example.com", 443, addresses=addresses, timeout=5.0, context=context
        )

        conn.connect()

        assert connected_to == [addresses]
        context.wrap_socket.assert_called_once_with(
            pinned, server_hostname="example.com"
        )


@pytest.mark.usefixtures("resolver")
class TestRedirects:
    def test_relative_redirect_keeps_the_host(self, server):
        response = fetch(_url(server, "/relative"), timeout=5.0, max_mb=1.0)

        assert response.body == _BODY
        assert response.url == _url(server, "/ok")
        hosts = {host for _, _, host in server.requests}
        assert hosts == {f"public.test:{server.server_address[1]}"}

    def test_each_hop_is_resolved_and_checked(self, server, resolver):
        target = _url(server, "/ok")
        fetch(_url(server, f"/redirect?to={quote(target)}"), timeout=5.0, max_mb=1.0)

        assert resolver == ["public.test", "public.test"]

    def test_redirect_to_a_private_host_is_refused(self, server):
        target = quote("http://internal.test/latest/meta-data/?sig=secret")
        with pytest.raises(BlockedURLError) as excinfo:
            fetch(_url(server, f"/redirect?to={target}"), timeout=5.0, max_mb=1.0)
        assert "secret" not in str(excinfo.value)
        assert len(server.requests) == 1

    @pytest.mark.parametrize(
        "target", ["file:///etc/passwd", "ftp://public.test/report.pdf"]
    )
    def test_redirect_to_another_scheme_is_refused(self, server, target):
        with pytest.raises(BlockedURLError, match="only http and https"):
            fetch(
                _url(server, f"/redirect?to={quote(target)}"), timeout=5.0, max_mb=1.0
            )

    def test_hop_limit(self, server):
        with pytest.raises(
            ValueError, match=f"Stopped after {MAX_REDIRECTS} redirects"
        ):
            fetch(_url(server, "/loop"), timeout=5.0, max_mb=1.0)
        assert len(server.requests) == MAX_REDIRECTS + 1

    def test_redirect_without_location_raises(self, server):
        with pytest.raises(ValueError, match="no Location header"):
            fetch(_url(server, "/no-location"), timeout=5.0, max_mb=1.0)


@pytest.mark.usefixtures("resolver")
class TestSizeCap:
    def test_declared_length_over_the_cap_raises(self, server):
        with pytest.raises(ValueError, match="exceeds the"):
            fetch(_url(server, "/large"), timeout=5.0, max_mb=_TINY_MB)

    def test_declared_length_over_the_cap_reads_nothing(self):
        response = Mock(spec=http.client.HTTPResponse)
        response.length = 2000
        response.read.side_effect = AssertionError("body must not be read")

        with pytest.raises(ValueError, match="exceeds the"):
            read_capped(response, url="https://example.com/x.pdf", max_mb=_TINY_MB)

    def test_undeclared_length_over_the_cap_raises(self, server):
        with pytest.raises(ValueError, match="exceeds the"):
            fetch(_url(server, "/stream"), timeout=5.0, max_mb=_TINY_MB)

    def test_body_at_the_cap_is_returned(self, server):
        max_mb = len(_LARGE_BODY) / (1024 * 1024)
        assert (
            fetch(_url(server, "/stream"), timeout=5.0, max_mb=max_mb).body
            == _LARGE_BODY
        )
