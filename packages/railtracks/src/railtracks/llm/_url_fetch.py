"""Guarded HTTP fetch for attachment URLs that may come from end users.

Every hop is checked before it is fetched: only `http` and `https`, and only hosts
whose addresses are all public. The connection goes to the address that was
checked, so a second DNS answer cannot point it elsewhere, and HTTPS still verifies
the certificate against the hostname. Redirects are followed by hand, proxy
environment variables are ignored, and URLs in errors carry no query string.
"""

from __future__ import annotations

import http.client
import ipaddress
import socket
import ssl
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal
from urllib.parse import quote, urljoin, urlsplit

MAX_REDIRECTS = 10
_READ_CHUNK_BYTES = 64 * 1024
_REDIRECT_STATUSES = frozenset({301, 302, 303, 307, 308})
_ALLOWED_SCHEMES = {"http": 80, "https": 443}
# Networks `is_global` lets through on some Python versions or clouds.
_BLOCKED_NETWORKS = (
    ipaddress.ip_network("168.63.129.16/32"),  # Azure Wire Server
    ipaddress.ip_network("192.0.0.0/24"),  # global on older patch releases
    ipaddress.ip_network("fec0::/10"),  # deprecated IPv6 site-local
    ipaddress.ip_network("::/96"),  # deprecated IPv4-compatible IPv6
    ipaddress.ip_network("::ffff:0:0:0/96"),  # SIIT IPv4-translated
    ipaddress.ip_network("64:ff9b:1::/48"),  # local-use NAT64
)
_NAT64_PREFIX = ipaddress.ip_network("64:ff9b::/96")
# Characters left as-is when re-quoting a request target; `%` keeps existing escapes.
_TARGET_SAFE_CHARS = "/:@!$&'()*+,;=-._~%?"

_SockAddr = tuple[str, int] | tuple[str, int, int, int] | tuple[int, bytes]
_Address = tuple[socket.AddressFamily, _SockAddr]


class BlockedURLError(ValueError):
    """Raised when a URL uses a scheme or reaches an address the fetch refuses."""


@dataclass(frozen=True)
class FetchResponse:
    """A completed fetch.

    Attributes:
        url: The final URL, after redirects.
        headers: The final response's headers.
        body: The response body; empty for a `HEAD` request.
    """

    url: str
    headers: http.client.HTTPMessage
    body: bytes


def redact_url(url: str) -> str:
    """Return `url` without its credentials, query string or fragment, for errors and logs.

    Args:
        url: The URL to redact.

    Returns:
        str: `scheme://host[:port]/path`, or a placeholder if `url` cannot be parsed.
    """
    try:
        parts = urlsplit(url)
        host = parts.hostname or ""
        port = f":{parts.port}" if parts.port else ""
    except ValueError:
        return "<unparseable URL>"
    if ":" in host:
        host = f"[{host}]"
    return f"{parts.scheme}://{host}{port}{parts.path}"


def is_blocked_address(address: str) -> bool:
    """Return whether a resolved address must not be fetched from.

    Anything that is not globally routable is blocked, as is multicast and the
    networks in `_BLOCKED_NETWORKS`. IPv4 addresses carried inside IPv6 (mapped,
    NAT64 and 6to4) are checked as well. Unparseable addresses are blocked.

    Args:
        address: An IP address as returned by `socket.getaddrinfo`.

    Returns:
        bool: True if the address is blocked.
    """
    try:
        ip = ipaddress.ip_address(address)
    except ValueError:
        return True
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped is not None:
        ip = ip.ipv4_mapped
    candidates: list[ipaddress.IPv4Address | ipaddress.IPv6Address] = [ip]
    if isinstance(ip, ipaddress.IPv6Address):
        if ip.sixtofour is not None:
            candidates.append(ip.sixtofour)
        if ip in _NAT64_PREFIX:
            candidates.append(ipaddress.IPv4Address(int(ip) & 0xFFFFFFFF))
    return any(
        not candidate.is_global
        or candidate.is_multicast
        or any(candidate in network for network in _BLOCKED_NETWORKS)
        for candidate in candidates
    )


def _resolve(host: str, port: int, url: str) -> list[_Address]:
    """Resolve `host` and return its addresses, refusing the host if any is blocked."""
    infos = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    addresses: list[_Address] = []
    for family, _, _, _, sockaddr in infos:
        if not isinstance(sockaddr[0], str) or is_blocked_address(sockaddr[0]):
            raise BlockedURLError(
                f"Refused to fetch {redact_url(url)}: {host!r} resolves to a "
                f"non-public address ({sockaddr[0]})."
            )
        addresses.append((family, sockaddr))
    if not addresses:
        raise OSError(f"No addresses found for {host!r}.")
    return addresses


def _connect(addresses: Sequence[_Address], timeout: float | None) -> socket.socket:
    """Open a TCP connection to the first of `addresses` that accepts one."""
    last_error: OSError | None = None
    for family, sockaddr in addresses:
        sock = socket.socket(family, socket.SOCK_STREAM)
        try:
            sock.settimeout(timeout)
            sock.connect(sockaddr)
            return sock
        except OSError as e:
            sock.close()
            last_error = e
    raise last_error or OSError("No address to connect to.")


class _PinnedHTTPConnection(http.client.HTTPConnection):
    """An `HTTPConnection` that connects to pre-checked addresses instead of resolving `host`."""

    def __init__(
        self, host: str, port: int, *, addresses: Sequence[_Address], timeout: float
    ) -> None:
        super().__init__(host, port, timeout=timeout)
        self._addresses = addresses

    def connect(self) -> None:
        self.sock = _connect(self._addresses, self.timeout)


class _PinnedHTTPSConnection(http.client.HTTPSConnection):
    """An `HTTPSConnection` that connects to pre-checked addresses and verifies TLS against `host`."""

    def __init__(
        self,
        host: str,
        port: int,
        *,
        addresses: Sequence[_Address],
        timeout: float,
        context: ssl.SSLContext,
    ) -> None:
        super().__init__(host, port, timeout=timeout, context=context)
        self._addresses = addresses
        self._tls_context = context

    def connect(self) -> None:
        sock = _connect(self._addresses, self.timeout)
        try:
            self.sock = self._tls_context.wrap_socket(sock, server_hostname=self.host)
        except BaseException:
            sock.close()
            raise


def _open(
    url: str, method: Literal["GET", "HEAD"], timeout: float
) -> tuple[http.client.HTTPConnection, http.client.HTTPResponse]:
    """Check one URL and send a request to it, without following redirects."""
    parts = urlsplit(url)
    scheme = parts.scheme.lower()
    if scheme not in _ALLOWED_SCHEMES:
        raise BlockedURLError(
            f"Refused to fetch {redact_url(url)}: only http and https URLs are fetched."
        )
    host = parts.hostname
    if not host:
        raise BlockedURLError(f"Refused to fetch {redact_url(url)}: it has no host.")
    port = parts.port or _ALLOWED_SCHEMES[scheme]
    addresses = _resolve(host, port, url)
    conn: http.client.HTTPConnection
    if scheme == "https":
        conn = _PinnedHTTPSConnection(
            host,
            port,
            addresses=addresses,
            timeout=timeout,
            context=ssl.create_default_context(),
        )
    else:
        conn = _PinnedHTTPConnection(host, port, addresses=addresses, timeout=timeout)
    target = quote(parts.path or "/", safe=_TARGET_SAFE_CHARS)
    if parts.query:
        target += "?" + quote(parts.query, safe=_TARGET_SAFE_CHARS)
    try:
        conn.request(
            method,
            target,
            headers={"User-Agent": "railtracks", "Accept-Encoding": "identity"},
        )
        return conn, conn.getresponse()
    except http.client.HTTPException as e:
        conn.close()
        raise ValueError(f"Bad HTTP response from {redact_url(url)}: {e!r}") from e
    except BaseException:
        conn.close()
        raise


def read_capped(
    response: http.client.HTTPResponse, *, url: str, max_mb: float
) -> bytes:
    """Read a response body in chunks, stopping once it passes `max_mb`.

    Args:
        response: The response to read.
        url: The URL the response came from, for error messages.
        max_mb: Largest body accepted, in megabytes.

    Returns:
        bytes: The complete body.

    Raises:
        ValueError: If the body exceeds `max_mb`, is malformed, or ends before
            its declared `Content-Length` or final chunk.
    """
    max_bytes = int(max_mb * 1024 * 1024)
    too_large = f"Download from {redact_url(url)} exceeds the {max_mb} MB limit."
    declared = response.length
    if isinstance(declared, int) and declared > max_bytes:
        raise ValueError(too_large)
    chunks: list[bytes] = []
    total = 0
    try:
        while chunk := response.read(_READ_CHUNK_BYTES):
            total += len(chunk)
            if total > max_bytes:
                raise ValueError(too_large)
            chunks.append(chunk)
    except http.client.IncompleteRead as e:
        raise ValueError(f"Download from {redact_url(url)} ended early: {e!r}") from e
    except http.client.HTTPException as e:
        raise ValueError(f"Bad HTTP response from {redact_url(url)}: {e!r}") from e
    # Bytes still owed under Content-Length; None when the server sent none.
    missing = response.length
    if isinstance(missing, int) and missing > 0:
        raise ValueError(
            f"Download from {redact_url(url)} ended {missing} bytes short of its "
            "Content-Length."
        )
    return b"".join(chunks)


def fetch(
    url: str,
    *,
    method: Literal["GET", "HEAD"] = "GET",
    timeout: float,
    max_mb: float | None = None,
) -> FetchResponse:
    """Fetch a URL that may come from an end user, guarding every hop.

    Args:
        url: The `http` or `https` URL to fetch.
        method: `GET` to download the body, `HEAD` for the headers only.
        timeout: Timeout in seconds for each connection and socket read.
        max_mb: Largest body accepted, in megabytes. Required for `GET`.

    Returns:
        FetchResponse: The final URL, its headers and its body.

    Raises:
        BlockedURLError: If any hop is not `http`/`https` or resolves to a
            non-public address.
        ValueError: On a malformed response, a non-2xx final status, more than
            `MAX_REDIRECTS` redirects, a redirect without a `Location`, or a
            body that is too large or cut short.
        OSError: If the host cannot be resolved or reached, or a read times out.
    """
    if method == "GET" and max_mb is None:
        raise ValueError("max_mb is required for a GET fetch.")
    for _ in range(MAX_REDIRECTS + 1):
        conn, response = _open(url, method, timeout)
        try:
            status = response.status
            if status in _REDIRECT_STATUSES:
                location = response.headers.get("Location")
                if not location:
                    raise ValueError(
                        f"Redirect from {redact_url(url)} has no Location header."
                    )
                url = urljoin(url, location.strip())
                continue
            if not 200 <= status < 300:
                raise ValueError(f"HTTP {status} from {redact_url(url)}.")
            body = (
                read_capped(response, url=url, max_mb=max_mb)
                if max_mb is not None and method == "GET"
                else b""
            )
            return FetchResponse(url=url, headers=response.headers, body=body)
        finally:
            response.close()
            conn.close()
    raise ValueError(f"Stopped after {MAX_REDIRECTS} redirects at {redact_url(url)}.")
