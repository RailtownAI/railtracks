import base64
import http.client
import math
import os
import re
from pathlib import Path
from typing import Literal
from urllib import error, request
from urllib.parse import urlparse

from .attachment_formats import detect_attachment_mime_from_bytes

DEFAULT_MAX_DOWNLOAD_MB = 32.0
_READ_CHUNK_BYTES = 64 * 1024


def validate_max_mb(max_mb: float, *, name: str = "max_mb") -> None:
    """Raise a `ValueError` unless `max_mb` is a positive, finite number.

    Args:
        max_mb: The download size limit, in megabytes.
        name: The parameter name shown in the error message.
    """
    if not 0 < max_mb < math.inf:
        raise ValueError(f"{name} must be a positive, finite number, got {max_mb!r}.")


def _is_base64_attachment(s: str) -> bool:
    """
    Return True if s appears to be a base64-encoded attachment payload (image or PDF),
    not a full data URI. Attempts a strict decode first, then a tolerant decode if needed.
    """
    s_stripped = s.strip()
    # fast reject common non-base64 characters (allow padding and urlsafe variants)
    if not re.fullmatch(r"[A-Za-z0-9+/=\s]+", s_stripped):
        # could still be urlsafe base64 without +/; try replace
        if re.fullmatch(r"[A-Za-z0-9\-_=\s]+", s_stripped) is None:
            return False

    try:
        decoded = base64.b64decode(s_stripped, validate=True)
    except Exception:
        # try tolerant decode with padding
        try:
            padding = "=" * ((4 - len(s_stripped) % 4) % 4)
            decoded = base64.b64decode(s_stripped + padding)
        except Exception:
            return False

    return detect_attachment_mime_from_bytes(decoded) is not None


def _validate_data_uri_header(header: str) -> bool:
    # Expect pattern like: data:image/{type};base64, or data:application/pdf;base64,
    return bool(
        re.match(
            r"^data:(image/[a-z0-9.+-]+|application/pdf);base64,$", header, flags=re.I
        )
    )


def ensure_data_uri(base64_or_data_uri: str) -> str:
    """
    If input is a valid data URI (with header), use as-is.
    Otherwise, detect attachment type and construct header dynamically.
    Raises ValueError on malformed input or unknown attachment type.
    """
    s = base64_or_data_uri.strip()
    if s.startswith("data:"):
        try:
            header, payload = s.split(",", 1)
        except ValueError:
            raise ValueError(
                "Incomplete data URI: missing comma separating header and base64 payload"
            )
        header_with_comma = header + ","
        if not _validate_data_uri_header(header_with_comma):
            raise ValueError(
                f"Malformed data URI header. Expected format like 'data:image/png;base64,' or 'data:application/pdf;base64,'. Got: {header_with_comma}"
            )
        return header_with_comma + payload

    # Otherwise treat as plain base64: try to decode some bytes to detect MIME
    try:
        decoded = base64.b64decode(s, validate=True)
    except Exception as e:
        try:
            decoded = base64.b64decode(s + ("=" * ((4 - len(s) % 4) % 4)))
        except Exception:
            raise ValueError("Provided string is not valid base64 or a data URI") from e

    mime = detect_attachment_mime_from_bytes(decoded)
    if not mime:
        raise ValueError(
            "Could not detect MIME type from provided base64 data. Provide a proper data URI or a supported attachment (image or PDF)."
        )
    return f"data:{mime};base64," + s


def detect_source(path: str) -> Literal["local", "url", "data_uri"]:
    """Detects whether the image path is a local file, URL, or data URI/base64.

    Args:
        path (str): The path/URL/base64 to check.

    Returns:
        str: One of "local", "url", or "data_uri"

    Raises:
        ValueError: If the path is invalid or cannot be determined.
    """
    # If it's already a data URI, treat as data_uri
    if path.startswith("data:"):
        return "data_uri"

    # If it's a plain base64-encoded attachment payload (image or PDF), treat as data_uri too
    if _is_base64_attachment(path):
        return "data_uri"

    parsed = urlparse(path)

    if parsed.scheme in ("http", "https", "ftp", "ftps"):
        return "url"

    if (
        not parsed.scheme
        or parsed.scheme == "file"
        or (len(parsed.scheme) == 1 and os.name == "nt")
    ):
        return "local"

    raise ValueError(f"Could not determine image source type for: {path}")


def _download_capped(path: str, *, timeout: float, max_mb: float) -> bytes:
    """Download a URL body in chunks, stopping once it passes `max_mb`.

    Args:
        path: The URL to download.
        timeout: Per-request timeout in seconds.
        max_mb: Largest body accepted, in megabytes.

    Returns:
        bytes: The complete body.

    Raises:
        ValueError: If the server returns an HTTP error, the body exceeds
            `max_mb`, or the body ends before its declared `Content-Length`
            or final chunk.
    """
    max_bytes = int(max_mb * 1024 * 1024)
    chunks: list[bytes] = []
    total = 0
    try:
        with request.urlopen(path, timeout=timeout) as url:
            while chunk := url.read(_READ_CHUNK_BYTES):
                total += len(chunk)
                if total > max_bytes:
                    raise ValueError(
                        f"Download from {path!r} exceeds the {max_mb} MB limit."
                    )
                chunks.append(chunk)
            # Bytes still owed under Content-Length; None when the server sent none.
            missing = getattr(url, "length", None)
    except error.HTTPError as e:
        raise ValueError(f"Failed to encode URL: {path}. Error: {e!r}") from e
    except http.client.IncompleteRead as e:
        raise ValueError(f"Download from {path!r} ended early: {e!r}") from e
    if isinstance(missing, int) and missing > 0:
        raise ValueError(
            f"Download from {path!r} ended {missing} bytes short of its Content-Length."
        )
    return b"".join(chunks)


def encode(
    path: str, *, timeout: float = 10.0, max_mb: float = DEFAULT_MAX_DOWNLOAD_MB
) -> str:
    """Encodes image/audio located at path to a Base64 string.

    Args:
        path: The path to the local file or URL to encode.
        timeout: Per-request timeout in seconds for URL fetches.
        max_mb: Largest body accepted from a URL, in megabytes. Must be positive
            and finite. The body is read in chunks and the download stops as soon
            as it passes the limit. Local files are not limited.

    Returns:
        str: Base64 encoded string

    Raises:
        FileNotFoundError: If the file doesn't exist.
        ValueError: If `max_mb` is not positive and finite, the path is not a
            local file, a URL body exceeds `max_mb`, or a URL body ends before
            its declared `Content-Length` or final chunk.
    """
    validate_max_mb(max_mb)
    source_type = detect_source(path)

    encoding = ""

    match source_type:
        case "local":
            file_path = Path(path)
            if not file_path.exists():
                raise FileNotFoundError(f"File not found: {path}")
            if not file_path.is_file():
                raise ValueError(f"Path is not a file: {path}")
            with open(path, "rb") as image_file:
                encoding = base64.b64encode(image_file.read()).decode("utf-8")
        case "url":
            data = _download_capped(path, timeout=timeout, max_mb=max_mb)
            encoding = base64.b64encode(data).decode("utf-8")
        case "data_uri":
            raise ValueError("Data is already in byte64 encoded format.")
        case _:
            raise ValueError(f"Unsupported source type: {source_type}")

    if not encoding:
        raise ValueError("Failed to encode image.")
    else:
        return encoding
