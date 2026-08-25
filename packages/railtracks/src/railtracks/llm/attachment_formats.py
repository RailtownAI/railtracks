"""Attachment format magic byte patterns and MIME type detection (images + documents)."""

import base64
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


def _convert_yaml_to_python(formats: dict[str, Any]) -> tuple[list, list]:
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
            item["offset_start"],
            item["offset_end"],
            item["fixed_bytes"].encode("utf-8"),
            {b.encode("utf-8") for b in item.get("variable_bytes", [])},
            item["mime_type"],
        )
        for item in formats.get("offset_formats", [])
    ]

    return prefix_formats, offset_formats


# Load formats at module initialization
_formats = _load_attachment_formats()
PREFIX_FORMATS, OFFSET_FORMATS = _convert_yaml_to_python(_formats)


def detect_attachment_mime_from_bytes(b: bytes) -> str | None:
    """Return MIME type for supported attachment formats by inspecting magic bytes.

    Covers images and documents declared in `attachment_formats.yaml`. Add a new
    format by appending a row there; no code changes needed.
    """
    if not b:
        return None

    for magic_bytes, mime_type in PREFIX_FORMATS:
        if b.startswith(magic_bytes):
            return mime_type

    for start, end, fixed_bytes, variable_bytes, mime_type in OFFSET_FORMATS:
        if b.startswith(fixed_bytes):
            if len(b) > end and b[start:end] in variable_bytes:
                return mime_type

    # SVG/XML detection is content-based, not magic-byte-based.
    head = b[:256].lower()
    if b"<svg" in head or head.lstrip().startswith(b"<?xml"):
        return "image/svg+xml"

    return None


def detect_image_mime_from_bytes(b: bytes) -> str | None:
    """Return MIME type for image formats only, or None for non-image / unknown bytes."""
    mime = detect_attachment_mime_from_bytes(b)
    return mime if mime and mime.startswith("image/") else None
