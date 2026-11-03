import base64
import datetime
import gzip
import ipaddress
import socket
import ssl
import threading
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import cast
from unittest.mock import Mock
from urllib.parse import quote, unquote

import httpx
import pytest
from railtracks.llm import _url_fetch
from railtracks.llm._url_fetch import (
    MAX_REDIRECTS,
    BlockedURLError,
    _read_capped,
    fetch,
    is_blocked_address,
    redact_url,
)
from railtracks.llm.message import Attachment

_BODY = b"hello"
_LARGE_BODY = b"x" * 2000
_GZIP_BODY = gzip.compress(_LARGE_BODY * 50)
_TINY_MB = 1000 / (1024 * 1024)  # 1000 bytes
_HOSTS = {
    "public.test": ["127.0.0.1"],
    "internal.test": ["10.0.0.1"],
    "mixed.test": ["127.0.0.1", "10.0.0.1"],
    "fallback.test": ["127.0.0.2", "127.0.0.1"],
}


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
        _ROUTES.get(path, _Handler._default)(self, query, send_body)

    def _default(self, query: str, send_body: bool) -> None:
        self._ok(_BODY, send_body=send_body)

    def _raw(self, data: bytes) -> None:
        self.wfile.write(data)

    def _ok(self, body: bytes, *, send_body: bool) -> None:
        self.send_response(200)
        self.send_header("Content-Type", "application/pdf")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        if send_body:
            self.wfile.write(body)

    def _status(self, status: int, headers: dict[str, str], body: bytes = b"") -> None:
        self.send_response(status)
        for name, value in headers.items():
            self.send_header(name, value)
        self.end_headers()
        self.wfile.write(body)

    def _redirect(self, location: str) -> None:
        self._status(302, {"Location": location, "Content-Length": "0"})

    def _slow(self, send_body: bool) -> None:
        time.sleep(0.5)
        self._ok(_BODY, send_body=send_body)


_Route = Callable[[_Handler, str, bool], None]
_ROUTES: dict[str, _Route] = {
    "/redirect": lambda h, query, _: h._redirect(unquote(query.removeprefix("to="))),
    "/relative": lambda h, *_: h._redirect("/ok"),
    "/loop": lambda h, *_: h._redirect("/loop"),
    "/no-location": lambda h, *_: h._status(302, {}),
    "/missing": lambda h, *_: h._status(404, {"Content-Length": "0"}),
    "/garbage": lambda h, *_: h._raw(b"garbage\r\n\r\n"),
    "/large": lambda h, _, send_body: h._ok(_LARGE_BODY, send_body=send_body),
    # HTTP/1.0 without Content-Length: the body ends when the connection closes.
    "/stream": lambda h, _, send_body: h._status(
        200, {}, _LARGE_BODY if send_body else b""
    ),
    "/truncated": lambda h, *_: h._status(
        200, {"Content-Length": "1000"}, b"%PDF-1.4 cut"
    ),
    "/truncated-chunked": lambda h, *_: h._raw(
        b"HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\n\r\n64\r\n%PDF-1.4"
    ),
    "/gzip": lambda h, *_: h._status(
        200,
        {"Content-Encoding": "gzip", "Content-Length": str(len(_GZIP_BODY))},
        _GZIP_BODY,
    ),
    "/slow": lambda h, _, send_body: h._slow(send_body),
}


@contextmanager
def _serve(tls: ssl.SSLContext | None = None) -> Iterator[_Server]:
    httpd = _Server(("127.0.0.1", 0), _Handler)
    httpd.requests = []
    if tls is not None:
        httpd.socket = tls.wrap_socket(httpd.socket, server_side=True)
    thread = threading.Thread(
        target=httpd.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True
    )
    thread.start()
    try:
        yield httpd
    finally:
        httpd.shutdown()
        httpd.server_close()


@pytest.fixture
def server() -> Iterator[_Server]:
    with _serve() as httpd:
        yield httpd


def _install_dns(
    monkeypatch: pytest.MonkeyPatch, answer: Callable[[str], list[str]]
) -> list[str]:
    """Answer hostname lookups with `answer`, pass IP literals through, and treat loopback as public.

    Returns:
        The hostnames looked up, in order.
    """
    lookups: list[str] = []

    def fake_getaddrinfo(host, port, *args, **kwargs):
        try:
            ips = [str(ipaddress.ip_address(host))]
        except ValueError:
            lookups.append(host)
            ips = answer(host)
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (ip, port)) for ip in ips]

    real_is_blocked = _url_fetch.is_blocked_address
    monkeypatch.setattr(
        _url_fetch,
        "is_blocked_address",
        lambda address, **_: real_is_blocked(address, allow_loopback=True),
    )
    monkeypatch.setattr(socket, "getaddrinfo", fake_getaddrinfo)
    return lookups


@pytest.fixture
def resolver(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Fake DNS over `_HOSTS`, where the local test server counts as a public address."""

    def lookup(host: str) -> list[str]:
        if host not in _HOSTS:
            raise socket.gaierror(f"unknown test host {host!r}")
        return _HOSTS[host]

    return _install_dns(monkeypatch, lookup)


@pytest.fixture
def no_connect(monkeypatch: pytest.MonkeyPatch) -> None:
    def boom_send(transport, request):
        raise AssertionError(f"must not send {request!r}")

    monkeypatch.setattr(httpx.HTTPTransport, "handle_request", boom_send)


def _url(
    server: _Server, path: str, host: str = "public.test", scheme: str = "http"
) -> str:
    return f"{scheme}://{host}:{server.server_address[1]}{path}"


def _tls_contexts(
    tmp_path: Path, cert_hostname: str
) -> tuple[ssl.SSLContext, ssl.SSLContext]:
    """Return a server context with a certificate for `cert_hostname` and a client context that trusts its CA."""
    pytest.importorskip("cryptography")
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID

    now = datetime.datetime.now(datetime.timezone.utc)
    ca_key = ec.generate_private_key(ec.SECP256R1())
    ca_name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "railtracks test CA")])
    ca_cert = (
        x509.CertificateBuilder()
        .subject_name(ca_name)
        .issuer_name(ca_name)
        .public_key(ca_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - datetime.timedelta(days=1))
        .not_valid_after(now + datetime.timedelta(days=1))
        .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
        .add_extension(
            x509.KeyUsage(
                digital_signature=True,
                content_commitment=False,
                key_encipherment=False,
                data_encipherment=False,
                key_agreement=False,
                key_cert_sign=True,
                crl_sign=True,
                encipher_only=False,
                decipher_only=False,
            ),
            critical=True,
        )
        .add_extension(
            x509.SubjectKeyIdentifier.from_public_key(ca_key.public_key()),
            critical=False,
        )
        .sign(ca_key, hashes.SHA256())
    )
    leaf_key = ec.generate_private_key(ec.SECP256R1())
    leaf_cert = (
        x509.CertificateBuilder()
        .subject_name(
            x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, cert_hostname)])
        )
        .issuer_name(ca_name)
        .public_key(leaf_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - datetime.timedelta(days=1))
        .not_valid_after(now + datetime.timedelta(days=1))
        .add_extension(
            x509.SubjectAlternativeName([x509.DNSName(cert_hostname)]),
            critical=False,
        )
        .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
        .add_extension(
            x509.ExtendedKeyUsage([ExtendedKeyUsageOID.SERVER_AUTH]), critical=False
        )
        .add_extension(
            x509.AuthorityKeyIdentifier.from_issuer_public_key(ca_key.public_key()),
            critical=False,
        )
        .sign(ca_key, hashes.SHA256())
    )
    ca_file = tmp_path / "ca.pem"
    ca_file.write_bytes(ca_cert.public_bytes(serialization.Encoding.PEM))
    cert_file = tmp_path / "cert.pem"
    cert_file.write_bytes(leaf_cert.public_bytes(serialization.Encoding.PEM))
    key_file = tmp_path / "key.pem"
    key_file.write_bytes(
        leaf_key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
    )
    server_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    server_context.minimum_version = ssl.TLSVersion.TLSv1_2
    server_context.load_cert_chain(cert_file, key_file)
    return server_context, ssl.create_default_context(cafile=ca_file)


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

    def test_invalid_url_is_a_value_error(self):
        with pytest.raises(ValueError, match="Invalid URL"):
            fetch("http://example.com:notaport/x", timeout=1.0, max_mb=1.0)

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

    def test_credentials_in_the_url_are_not_sent(self, server, monkeypatch):
        sent: list[httpx.Request] = []
        real_send = httpx.HTTPTransport.handle_request

        def record_send(transport, request):
            sent.append(request)
            return real_send(transport, request)

        monkeypatch.setattr(httpx.HTTPTransport, "handle_request", record_send)
        url = _url(server, "/ok", host="user:pw@public.test")

        assert fetch(url, timeout=5.0, max_mb=1.0).body == _BODY
        assert "Authorization" not in sent[0].headers

    def test_any_blocked_address_refuses_the_host(self, server):
        with pytest.raises(
            BlockedURLError, match=r"non-public address \(10\.0\.0\.1\)"
        ):
            fetch(_url(server, "/ok", host="mixed.test"), timeout=5.0, max_mb=1.0)
        assert server.requests == []

    def test_unreachable_address_falls_back_to_the_next(self, server, monkeypatch):
        tried: list[str] = []
        real_send = httpx.HTTPTransport.handle_request

        def flaky_send(transport, request):
            tried.append(request.url.host)
            if request.url.host == "127.0.0.2":
                raise httpx.ConnectError("connection refused")
            return real_send(transport, request)

        monkeypatch.setattr(httpx.HTTPTransport, "handle_request", flaky_send)
        url = _url(server, "/ok", host="fallback.test")

        assert fetch(url, timeout=5.0, max_mb=1.0).body == _BODY
        assert tried == ["127.0.0.2", "127.0.0.1"]

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

    def test_read_timeout_is_an_os_error(self, server):
        with pytest.raises(OSError, match="ReadTimeout"):
            fetch(_url(server, "/slow"), timeout=0.1, max_mb=1.0)


@pytest.mark.usefixtures("resolver")
class TestTls:
    def test_https_request_is_pinned_with_the_hostname_for_tls(self, monkeypatch):
        sent: list[httpx.Request] = []

        def capture_send(transport, request):
            sent.append(request)
            raise httpx.ConnectError("stop before the network")

        monkeypatch.setattr(httpx.HTTPTransport, "handle_request", capture_send)
        with pytest.raises(OSError, match="stop before the network"):
            fetch("https://public.test/report.pdf", timeout=5.0, max_mb=1.0)

        assert sent[0].url.host == "127.0.0.1"
        assert sent[0].headers["Host"] == "public.test"
        assert sent[0].extensions["sni_hostname"] == "public.test"

    def test_certificate_for_the_hostname_is_accepted(self, tmp_path, monkeypatch):
        server_context, client_context = _tls_contexts(tmp_path, "public.test")
        monkeypatch.setattr(httpx, "create_ssl_context", lambda: client_context)

        with _serve(server_context) as httpd:
            response = fetch(
                _url(httpd, "/ok", scheme="https"), timeout=5.0, max_mb=1.0
            )

        assert response.body == _BODY

    def test_certificate_for_another_host_is_refused(self, tmp_path, monkeypatch):
        server_context, client_context = _tls_contexts(tmp_path, "other.test")
        monkeypatch.setattr(httpx, "create_ssl_context", lambda: client_context)

        with _serve(server_context) as httpd:
            with pytest.raises(OSError, match="certificate verify failed"):
                fetch(_url(httpd, "/ok", scheme="https"), timeout=5.0, max_mb=1.0)
            assert httpd.requests == []


class TestAllowLoopback:
    @pytest.mark.parametrize(
        "address", ["127.0.0.1", "127.8.9.10", "::1", "::ffff:127.0.0.1"]
    )
    def test_loopback_is_allowed(self, address):
        assert is_blocked_address(address, allow_loopback=True) is False

    @pytest.mark.parametrize(
        "address",
        [
            "10.0.0.1",
            "192.168.1.1",
            "169.254.169.254",
            "0.0.0.0",
            "::",
            "fe80::1",
            "2002:7f00:1::1",  # 6to4 of 127.0.0.1
            "64:ff9b::7f00:1",  # NAT64 of 127.0.0.1
        ],
    )
    def test_other_non_public_addresses_stay_blocked(self, address):
        assert is_blocked_address(address, allow_loopback=True) is True

    def test_loopback_server_is_fetched_only_when_allowed(self, server):
        url = _url(server, "/ok", host="127.0.0.1")
        with pytest.raises(BlockedURLError, match="non-public address"):
            fetch(url, timeout=5.0, max_mb=1.0)
        assert server.requests == []

        assert fetch(url, timeout=5.0, max_mb=1.0, allow_loopback=True).body == _BODY

    def test_redirect_to_a_private_host_is_still_refused(self, server):
        target = quote("http://10.0.0.1/latest/meta-data/")
        url = _url(server, f"/redirect?to={target}", host="127.0.0.1")
        with pytest.raises(BlockedURLError, match=r"10\.0\.0\.1"):
            fetch(url, timeout=5.0, max_mb=1.0, allow_loopback=True)

    def test_attachment_downloads_a_loopback_pdf(self, server):
        url = _url(server, "/report.pdf", host="127.0.0.1")
        with pytest.raises(BlockedURLError):
            Attachment(url, trust_urls=True)

        attachment = Attachment(url, trust_urls=True, allow_loopback_urls=True)

        assert attachment.modality == "document"
        assert attachment.encoding == (
            "data:application/pdf;base64," + base64.b64encode(_BODY).decode("ascii")
        )


class TestDnsRebinding:
    def test_connects_to_the_checked_address(self, server, monkeypatch):
        """A second DNS answer pointing at a private address is never used."""
        answers = iter([["127.0.0.1"], ["10.0.0.1"]])
        lookups = _install_dns(monkeypatch, lambda host: next(answers))

        response = fetch(
            _url(server, "/ok", host="rebind.test"), timeout=5.0, max_mb=1.0
        )

        assert response.body == _BODY
        assert lookups == ["rebind.test"]


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
class TestBody:
    def test_declared_length_over_the_cap_raises(self, server):
        with pytest.raises(ValueError, match="exceeds the"):
            fetch(_url(server, "/large"), timeout=5.0, max_mb=_TINY_MB)

    def test_declared_length_over_the_cap_reads_nothing(self):
        response = Mock(spec=httpx.Response)
        response.headers = httpx.Headers({"Content-Length": "2000"})
        response.iter_raw.side_effect = AssertionError("body must not be read")

        with pytest.raises(ValueError, match="exceeds the"):
            _read_capped(response, url="https://example.com/x.pdf", max_mb=_TINY_MB)

    def test_undeclared_length_over_the_cap_raises(self, server):
        with pytest.raises(ValueError, match="exceeds the"):
            fetch(_url(server, "/stream"), timeout=5.0, max_mb=_TINY_MB)

    def test_body_at_the_cap_is_returned(self, server):
        max_mb = len(_LARGE_BODY) / (1024 * 1024)
        assert (
            fetch(_url(server, "/stream"), timeout=5.0, max_mb=max_mb).body
            == _LARGE_BODY
        )

    def test_large_cap_does_not_reserve_memory(self, server):
        body = fetch(_url(server, "/stream"), timeout=5.0, max_mb=1_000_000).body

        assert body == _LARGE_BODY

    def test_compressed_body_is_counted_and_returned_raw(self, server):
        """Bytes are capped as sent, so a small gzip body cannot inflate past the cap."""
        body = fetch(_url(server, "/gzip"), timeout=5.0, max_mb=_TINY_MB).body

        assert body == _GZIP_BODY

    @pytest.mark.parametrize("path", ["/truncated", "/truncated-chunked"])
    def test_truncated_body_raises(self, server, path):
        with pytest.raises(ValueError, match="Bad HTTP response"):
            fetch(_url(server, f"{path}?sig=secret"), timeout=5.0, max_mb=1.0)
