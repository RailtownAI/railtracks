"""Attachment format detection: MIME types from magic bytes or from a file extension."""

import base64
import functools
import mimetypes
import os
from pathlib import Path
from typing import Any

import yaml


def _load_attachment_formats() -> dict[str, Any]:
    """Load attachment format definitions from YAML file."""
    formats_file = Path(__file__).parent / "attachment_formats.yaml"

    if not formats_file.exists():
        raise FileNotFoundError(f"Attachment formats file not found: {formats_file}")

    with open(formats_file) as f:
        return yaml.safe_load(f)


def _convert_yaml_to_python(
    formats: dict[str, Any],
) -> tuple[
    list[tuple[bytes, str]],
    list[tuple[int, int, int, bytes, set[bytes], str]],
    dict[str, str],
]:
    """Convert YAML format definitions to Python data structures."""
    prefix_formats = []
    for item in formats.get("prefix_formats", []):
        # Handle base64-encoded magic bytes
        if "magic_bytes_b64" in item:
            magic = base64.b64decode(item["magic_bytes_b64"])
        elif "magic_bytes" in item:
            magic = item["magic_bytes"].encode("utf-8")
        else:
            raise ValueError(
                f"Format item missing magic_bytes or magic_bytes_b64: {item}"
            )
        prefix_formats.append((magic, item["mime_type"]))

    offset_formats = [
        (
            item.get("fixed_offset", 0),
            item["offset_start"],
            item["offset_end"],
            item["fixed_bytes"].encode("utf-8"),
            {b.encode("utf-8") for b in item.get("variable_bytes", [])},
            item["mime_type"],
        )
        for item in formats.get("offset_formats", [])
    ]

    extension_formats = {
        extension: item["mime_type"]
        for section in ("prefix_formats", "offset_formats", "extension_formats")
        for item in formats.get(section, [])
        for extension in item.get("extensions", [])
    }

    return prefix_formats, offset_formats, extension_formats


# Load formats at module initialization
_formats = _load_attachment_formats()
PREFIX_FORMATS, OFFSET_FORMATS, EXTENSION_FORMATS = _convert_yaml_to_python(_formats)
CONTAINER_FORMATS = frozenset(
    item["mime_type"]
    for section in ("prefix_formats", "offset_formats")
    for item in _formats.get(section, [])
    if item.get("container")
)


@functools.cache
def _stdlib_mimetypes() -> mimetypes.MimeTypes:
    # A fresh instance holds only Python's built-in table, not the OS registry,
    # so lookups match on every machine running the same Python version.
    return mimetypes.MimeTypes()


def detect_attachment_mime_from_bytes(b: bytes) -> str | None:
    """Return MIME type for supported attachment formats by inspecting magic bytes.

    Covers the images, documents, audio and video declared in
    `attachment_formats.yaml`. Add a new format by appending a row there; no code
    changes needed.
    """
    if not b:
        return None

    for magic_bytes, mime_type in PREFIX_FORMATS:
        if b.startswith(magic_bytes):
            return mime_type

    for (
        fixed_offset,
        start,
        end,
        fixed_bytes,
        variable_bytes,
        mime_type,
    ) in OFFSET_FORMATS:
        if b.startswith(fixed_bytes, fixed_offset):
            if len(b) >= end and b[start:end] in variable_bytes:
                return mime_type

    # SVG has no magic bytes; it must open the document, after an optional XML
    # declaration, comment or doctype, so HTML or Markdown with an inline <svg> is not one.
    head = b[:1024].lstrip().lower()
    if head.startswith((b"<svg", b"<?xml", b"<!--", b"<!doctype svg")) and (
        b"<svg" in head
    ):
        return "image/svg+xml"

    return None


def detect_mime(data: bytes, name: str | None = None) -> str | None:
    """Return the MIME type of file content, from its magic bytes, then its name.

    A container that can hold audio or video (Ogg, Matroska, MP4) takes the type
    its extension names when that is audio or video, so `clip.ogv` is video.

    Args:
        data: The file content.
        name: The file name or path, if known.

    Returns:
        The MIME type, or None when neither the bytes nor the name identify it.
    """
    magic = detect_attachment_mime_from_bytes(data)
    named = detect_mime_from_extension(name) if name else None
    if magic in CONTAINER_FORMATS and named:
        if named.split("/", 1)[0] in ("audio", "video"):
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
    return (
        EXTENSION_FORMATS.get(extension)
        or _stdlib_mimetypes().guess_type(f"file{extension}")[0]
    )


def detect_image_mime_from_bytes(b: bytes) -> str | None:
    """Return MIME type for image formats only, or None for non-image / unknown bytes."""
    mime = detect_attachment_mime_from_bytes(b)
    return mime if mime and mime.startswith("image/") else None
