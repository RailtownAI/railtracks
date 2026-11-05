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

AttachmentSource = Literal["local", "url", "data_uri"]
"""Where an attachment came from; `data_uri` covers every inline payload, raw bytes included."""

DEFAULT_MAX_DOWNLOAD_MB = 32.0
_READ_CHUNK_BYTES = 64 * 1024
_URLSAFE_TO_STANDARD = str.maketrans("-_", "+/")


def validate_max_mb(max_mb: float, *, name: str = "max_mb") -> None:
    """Raise a `ValueError` unless `max_mb` is a positive, finite number.

    Args:
        max_mb: The download size limit, in megabytes.
        name: The parameter name shown in the error message.
    """
    if not 0 < max_mb < math.inf:
        raise ValueError(f"{name} must be a positive, finite number, got {max_mb!r}.")


def _normalize_base64(s: str) -> str:
    """Convert base64 text to the standard alphabet with no whitespace and full padding.

    Args:
        s: Base64 text, possibly line-wrapped, unpadded, or URL-safe.

    Returns:
        Standard-alphabet base64 with a length that is a multiple of 4.
    """
    s = "".join(s.split()).translate(_URLSAFE_TO_STANDARD)
    return s + "=" * (-len(s) % 4)


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
        try:
            decoded = base64.b64decode(_normalize_base64(s_stripped))
        except Exception:
            return False

    return detect_attachment_mime_from_bytes(decoded) is not None


def _validate_data_uri_header(header: str) -> bool:
    # Expect pattern like: data:image/png;base64, or data:audio/wav;base64,
    return bool(
        re.match(r"^data:[a-z0-9.+-]+/[a-z0-9.+-]+;base64,$", header, flags=re.I)
    )


def _decode_base64(s: str) -> bytes:
    """Decode base64 text, tolerating line wrapping, missing padding and the URL-safe alphabet.

    Raises:
        ValueError: If `s` is not valid base64.
    """
    try:
        return base64.b64decode(s, validate=True)
    except ValueError as e:
        try:
            return base64.b64decode(_normalize_base64(s), validate=True)
        except ValueError:
            raise ValueError("Provided string is not valid base64 or a data URI") from e


def decode_data_uri(base64_or_data_uri: str) -> tuple[str, bytes]:
    """Split a data URI or plain base64 payload into its MIME type and raw bytes.

    Args:
        base64_or_data_uri: A `data:<mime>;base64,...` URI, or plain base64 whose
            MIME type is detected from its magic bytes.

    Returns:
        The lowercase MIME type and the decoded bytes.

    Raises:
        ValueError: If the URI is malformed, the payload is not valid base64, or the
            MIME type of plain base64 cannot be detected.
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
        mime = header[len("data:") :].split(";", 1)[0].lower()
        return mime, _decode_base64(payload)

    decoded = _decode_base64(s)
    mime = detect_attachment_mime_from_bytes(decoded)
    if not mime:
        raise ValueError(
            "Could not detect MIME type from provided base64 data. Provide a proper data URI or a supported attachment (image, audio, video or PDF)."
        )
    return mime, decoded


def ensure_data_uri(base64_or_data_uri: str) -> str:
    """Return a data URI with standard, padded base64 for a data URI or plain base64.

    Raises:
        ValueError: For the reasons listed on `decode_data_uri`.
    """
    mime, data = decode_data_uri(base64_or_data_uri)
    return f"data:{mime};base64,{base64.b64encode(data).decode('ascii')}"


def detect_source(path: str) -> AttachmentSource:
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


def load_bytes(
    path: str, *, timeout: float = 10.0, max_mb: float = DEFAULT_MAX_DOWNLOAD_MB
) -> bytes:
    """Read the bytes of a local file or URL.

    Args:
        path: The path to the local file or URL to read.
        timeout: Per-request timeout in seconds for URL fetches.
        max_mb: Largest body accepted from a URL, in megabytes. Must be positive
            and finite. The body is read in chunks and the download stops as soon
            as it passes the limit. Local files are not limited.

    Returns:
        bytes: The file or response body.

    Raises:
        FileNotFoundError: If the file doesn't exist.
        ValueError: If `max_mb` is not positive and finite, the path is a data URI
            or not a file, a URL body exceeds `max_mb`, or a URL body ends before
            its declared `Content-Length` or final chunk.
    """
    validate_max_mb(max_mb)
    source_type = detect_source(path)

    match source_type:
        case "local":
            file_path = Path(path)
            if not file_path.exists():
                raise FileNotFoundError(f"File not found: {path}")
            if not file_path.is_file():
                raise ValueError(f"Path is not a file: {path}")
            return file_path.read_bytes()
        case "url":
            return _download_capped(path, timeout=timeout, max_mb=max_mb)
        case "data_uri":
            raise ValueError("Data is already in byte64 encoded format.")
        case _:
            raise ValueError(f"Unsupported source type: {source_type}")


def encode(
    path: str, *, timeout: float = 10.0, max_mb: float = DEFAULT_MAX_DOWNLOAD_MB
) -> str:
    """Encodes the file located at path to a Base64 string.

    Args:
        path: The path to the local file or URL to encode.
        timeout: Per-request timeout in seconds for URL fetches.
        max_mb: Largest body accepted from a URL, in megabytes. Must be positive
            and finite. Local files are not limited.

    Returns:
        str: Base64 encoded string

    Raises:
        FileNotFoundError: If the file doesn't exist.
        ValueError: For the reasons listed on `load_bytes`, or if the file is empty.
    """
    data = load_bytes(path, timeout=timeout, max_mb=max_mb)
    if not data:
        raise ValueError("Failed to encode image.")
    return base64.b64encode(data).decode("utf-8")
