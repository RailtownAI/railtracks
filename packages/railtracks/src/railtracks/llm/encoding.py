import base64
import os
import re
from pathlib import Path
from typing import Literal
from urllib import error, request
from urllib.parse import urlparse

from .image_formats import detect_image_mime_from_bytes


def _is_base64_image(s: str) -> bool:
    """
    Return True if s appears to be a base64-encoded image payload (not a full data URI).
    This attempts a strict decode first, then a tolerant decode if needed.
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

    return detect_image_mime_from_bytes(decoded) is not None


def _validate_data_uri_header(header: str) -> bool:
    # Expect pattern like: data:image/{type};base64,
    return bool(re.match(r"^data:image/[a-z0-9.+-]+;base64,$", header, flags=re.I))


def ensure_data_uri(base64_or_data_uri: str) -> str:
    """
    If input is a valid data URI (with header), use as-is.
    Otherwise, detect image type and construct header dynamically.
    Raises ValueError on malformed input or unknown image type.
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
                f"Malformed data URI header. Expected format like 'data:image/png;base64,'. Got: {header_with_comma}"
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

    mime = detect_image_mime_from_bytes(decoded)
    if not mime:
        raise ValueError(
            "Could not detect image MIME type from provided base64 data. Provide a proper data URI or a known image file."
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

    # If it's a plain base64-encoded image payload, treat as data_uri too
    if _is_base64_image(path):
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


def encode(path: str) -> str:
    """Encodes image/audio loocated at path to a Base64 string.

    Args:
        path (str): The path to the local image file.

    Returns:
        str: Base64 encoded string

    Raises:
        FileNotFoundError: If the file doesn't exist.
        ValueError: If the path is not a local file.
    """
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
        case (
            "url"
        ):  # we will not encode urls for now but putting this here for future proofing
            try:
                with request.urlopen(path) as url:
                    encoding = base64.b64encode(url.read()).decode("utf-8")
            except error.HTTPError as e:
                raise ValueError(f"Failed to encode URL: {path}. Error: {e}")
        case "data_uri":
            raise ValueError("Data is already in byte64 encoded format.")
        case _:
            raise ValueError(f"Unsupported source type: {source_type}")

    if not encoding:
        raise ValueError("Failed to encode image.")
    else:
        return encoding
