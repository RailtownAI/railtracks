"""Guarded HTTP fetch for attachment URLs that may come from end users.

Every hop is checked before it is fetched: only `http` and `https`, and only hosts
whose addresses are all public. The request goes to the address that was checked,
so a second DNS answer cannot point it elsewhere, and HTTPS still verifies the
certificate against the hostname. Redirects are followed by hand, proxy
environment variables are ignored, and URLs in errors carry no query string.
"""

from __future__ import annotations

import ipaddress
import socket
from collections.abc import Iterator
from contextlib import closing, contextmanager
from dataclasses import dataclass
from typing import Literal
from urllib.parse import urljoin, urlsplit

import httpx

MAX_REDIRECTS = 10
_READ_CHUNK_BYTES = 64 * 1024
_REDIRECT_STATUSES = frozenset({301, 302, 303, 307, 308})
_ALLOWED_SCHEMES = {"http": 80, "https": 443}
_HEADERS = {"User-Agent": "railtracks", "Accept-Encoding": "identity"}
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
    headers: httpx.Headers
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


def is_blocked_address(address: str, *, allow_loopback: bool = False) -> bool:
    """Return whether a resolved address must not be fetched from.

    Anything that is not globally routable is blocked, as is multicast and the
    networks in `_BLOCKED_NETWORKS`. IPv4 addresses carried inside IPv6 (mapped,
    NAT64 and 6to4) are checked as well. Unparseable addresses are blocked.

    Args:
        address: An IP address as returned by `socket.getaddrinfo`.
        allow_loopback: Allow loopback addresses (`127.0.0.0/8`, `::1`), for
            local testing. Every other non-public address stays blocked.

    Returns:
        bool: True if the address is blocked.
    """
    try:
        ip = ipaddress.ip_address(address)
    except ValueError:
        return True
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped is not None:
        ip = ip.ipv4_mapped
    if allow_loopback and ip.is_loopback:
        return False
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


def _resolve(host: str, port: int, url: str, *, allow_loopback: bool) -> list[str]:
    """Resolve `host` and return its addresses, refusing the host if any is blocked."""
    addresses: list[str] = []
    for *_, sockaddr in socket.getaddrinfo(host, port, type=socket.SOCK_STREAM):
        address = sockaddr[0]
        if not isinstance(address, str) or is_blocked_address(
            address, allow_loopback=allow_loopback
        ):
            raise BlockedURLError(
                f"Refused to fetch {redact_url(url)}: {host!r} resolves to a "
                f"non-public address ({address})."
            )
        if address not in addresses:
            addresses.append(address)
    if not addresses:
        raise OSError(f"No addresses found for {host!r}.")
    return addresses


def _send(
    client: httpx.Client,
    url: str,
    method: Literal["GET", "HEAD"],
    *,
    allow_loopback: bool,
) -> httpx.Response:
    """Check one URL and send a request to it over a checked address, without following redirects."""
    try:
        target = httpx.URL(url).copy_with(username=None, password=None)
    except httpx.InvalidURL as e:
        raise ValueError(f"Invalid URL {redact_url(url)}: {e!r}") from e
    if target.scheme not in _ALLOWED_SCHEMES:
        raise BlockedURLError(
            f"Refused to fetch {redact_url(url)}: only http and https URLs are fetched."
        )
    host = target.raw_host.decode("ascii")
    if not host:
        raise BlockedURLError(f"Refused to fetch {redact_url(url)}: it has no host.")
    port = target.port or _ALLOWED_SCHEMES[target.scheme]
    addresses = _resolve(host, port, url, allow_loopback=allow_loopback)

    def request_to(address: str) -> httpx.Request:
        return client.build_request(
            method,
            target.copy_with(host=address),
            headers={"Host": target.netloc.decode("ascii")},
            extensions={"sni_hostname": host},
        )

    for address in addresses[:-1]:
        try:
            return client.send(request_to(address), stream=True)
        except httpx.ConnectError:
            continue
    return client.send(request_to(addresses[-1]), stream=True)


@contextmanager
def _mapped_errors(url: str) -> Iterator[None]:
    """Re-raise `httpx` errors as the `ValueError` or `OSError` that callers handle."""
    try:
        yield
    except httpx.ProtocolError as e:
        raise ValueError(f"Bad HTTP response from {redact_url(url)}: {e!r}") from e
    except httpx.TransportError as e:
        raise OSError(f"Could not fetch {redact_url(url)}: {e!r}") from e


def _read_capped(response: httpx.Response, *, url: str, max_mb: float) -> bytes:
    """Read a response body in chunks, stopping once it passes `max_mb`.

    Raw bytes are counted, so a compressed body cannot expand past the cap.
    """
    max_bytes = int(max_mb * 1024 * 1024)
    too_large = f"Download from {redact_url(url)} exceeds the {max_mb} MB limit."
    declared = response.headers.get("Content-Length")
    if declared is not None and int(declared) > max_bytes:
        raise ValueError(too_large)
    chunks: list[bytes] = []
    total = 0
    for chunk in response.iter_raw(_READ_CHUNK_BYTES):
        total += len(chunk)
        if total > max_bytes:
            raise ValueError(too_large)
        chunks.append(chunk)
    return b"".join(chunks)


def fetch(
    url: str,
    *,
    method: Literal["GET", "HEAD"] = "GET",
    timeout: float,
    max_mb: float | None = None,
    allow_loopback: bool = False,
) -> FetchResponse:
    """Fetch a URL that may come from an end user, guarding every hop.

    Args:
        url: The `http` or `https` URL to fetch.
        method: `GET` to download the body, `HEAD` for the headers only.
        timeout: Timeout in seconds for each connection and socket read.
        max_mb: Largest body accepted, in megabytes. Required for `GET`.
        allow_loopback: Allow hosts that resolve to loopback addresses, on
            every hop. Every other non-public address stays blocked.

    Returns:
        FetchResponse: The final URL, its headers and its body.

    Raises:
        BlockedURLError: If any hop is not `http`/`https` or resolves to a
            non-public address.
        ValueError: On an invalid URL, a malformed response, a non-2xx final
            status, more than `MAX_REDIRECTS` redirects, a redirect without a
            `Location`, or a body that is too large or cut short.
        OSError: If the host cannot be resolved or reached, the TLS
            certificate does not verify, or a read times out.
    """
    if method == "GET" and max_mb is None:
        raise ValueError("max_mb is required for a GET fetch.")
    with httpx.Client(
        headers=_HEADERS,
        timeout=timeout,
        verify=httpx.create_ssl_context(),
        trust_env=False,
    ) as client:
        for _ in range(MAX_REDIRECTS + 1):
            with (
                _mapped_errors(url),
                closing(
                    _send(client, url, method, allow_loopback=allow_loopback)
                ) as response,
            ):
                status = response.status_code
                if status not in _REDIRECT_STATUSES:
                    if not response.is_success:
                        raise ValueError(f"HTTP {status} from {redact_url(url)}.")
                    body = (
                        _read_capped(response, url=url, max_mb=max_mb)
                        if max_mb is not None and method == "GET"
                        else b""
                    )
                    return FetchResponse(url=url, headers=response.headers, body=body)
                location = response.headers.get("Location")
                if not location:
                    raise ValueError(
                        f"Redirect from {redact_url(url)} has no Location header."
                    )
                url = urljoin(url, location.strip())
    raise ValueError(f"Stopped after {MAX_REDIRECTS} redirects at {redact_url(url)}.")
