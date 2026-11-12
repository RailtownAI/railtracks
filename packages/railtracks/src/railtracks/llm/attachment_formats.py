"""Attachment format detection: MIME types from magic bytes or from a file extension."""

import functools
import mimetypes
import os
import re
from pathlib import Path
from typing import Any

import yaml

_UTF8_BOM = b"\xef\xbb\xbf"

# SVG has no magic bytes: its first tag, after any XML declaration, comments and SVG
# doctype, must be <svg>, so HTML or Markdown with an inline <svg> is not one.
_SVG_START = re.compile(
    # Each token ends at its first closing delimiter, so a failed match cannot backtrack.
    rb"(?:\s|<\?xml(?:[^?]|\?(?!>))*\?>|<!--(?:[^-]|-(?!->))*-->"
    rb"|<!doctype\s+svg(?:[^>\[]|\[[^\]]*\])*>)*<svg[\s/>]",
    re.DOTALL | re.IGNORECASE,
)

# WebM and Matroska share the EBML magic bytes; the header's DocType element tells them apart.
_MATROSKA_DOCTYPE = b"\x42\x82\x88matroska"
_EBML_HEADER_BYTES = 64

_Signature = tuple[tuple[int, tuple[bytes, ...]], ...]


def _signature(match: dict[int, str | list[str]]) -> _Signature:
    """Return a `match` map as (offset, allowed bytes) pairs, reading its text as latin-1."""
    return tuple(
        (offset, tuple(s.encode("latin-1") for s in ([b] if isinstance(b, str) else b)))
        for offset, b in match.items()
    )


_TABLE: dict[str, Any] = yaml.safe_load(
    (Path(__file__).parent / "attachment_formats.yaml").read_text(encoding="utf-8")
)
_FORMATS: list[dict[str, Any]] = _TABLE["formats"]
_SIGNATURES = [
    (row["mime_type"], _signature(row["match"])) for row in _FORMATS if "match" in row
]
CONTAINER_FORMATS: dict[str, frozenset[str]] = {
    row["mime_type"]: frozenset(row["container"])
    for row in _FORMATS
    if "container" in row
}
UNSUPPORTED_URL_EXTENSIONS = frozenset(_TABLE["unsupported_url_extensions"])


@functools.cache
def _mime_types() -> mimetypes.MimeTypes:
    # A fresh instance holds only Python's built-in table, not the OS registry, so
    # lookups match on every machine; the YAML extensions override it.
    types = mimetypes.MimeTypes()
    for row in _FORMATS:
        for extension in row.get("extensions", ()):
            types.add_type(row["mime_type"], extension)
    return types


def detect_attachment_mime_from_bytes(b: bytes) -> str | None:
    """Return MIME type for supported attachment formats by inspecting magic bytes.

    Covers the images, documents, audio and video declared in
    `attachment_formats.yaml`. Add a new format by appending a row there; no code
    changes needed.
    """
    for mime_type, signature in _SIGNATURES:
        if all(b.startswith(allowed, offset) for offset, allowed in signature):
            if (
                mime_type == "video/webm"
                and _MATROSKA_DOCTYPE in b[:_EBML_HEADER_BYTES]
            ):
                return "video/x-matroska"
            return mime_type

    if _SVG_START.match(b.removeprefix(_UTF8_BOM)):
        return "image/svg+xml"

    return None


def detect_mime(data: bytes, name: str | None = None) -> str | None:
    """Return the MIME type of file content, from its magic bytes, then its name.

    A container (Ogg, Matroska, MP4, HEIF) takes the type its extension names when
    that is a kind it can hold, so `clip.ogv` is video and `photo.avif` is AVIF.

    Args:
        data: The file content.
        name: The file name or path, if known.

    Returns:
        The MIME type, or None when neither the bytes nor the name identify it.
    """
    magic = detect_attachment_mime_from_bytes(data)
    named = detect_mime_from_extension(name) if name else None
    if named and named.split("/", 1)[0] in CONTAINER_FORMATS.get(magic or "", ()):
        return named
    return magic or named


def detect_mime_from_extension(name: str) -> str | None:
    """Return the MIME type for a file name, path or URL path by its extension.

    Extensions listed in `attachment_formats.yaml` win, so a name and its magic
    bytes agree on every Python version; Python's `mimetypes` covers the rest.

    Args:
        name: A file name, path or URL path.

    Returns:
        The MIME type, or None when the extension is missing or unknown.
    """
    extension = os.path.splitext(name)[1].lower()
    if not extension:
        return None
    return _mime_types().guess_type(f"file{extension}")[0]
