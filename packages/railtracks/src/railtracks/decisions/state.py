"""What a decision is about: text, JSON, or a ``DecisionState`` with image attachments."""

from __future__ import annotations

import base64
from collections.abc import Sequence
from pathlib import Path
from typing import Any, Union

from typing_extensions import TypeAlias

from railtracks.llm.attachment_formats import detect_attachment_mime_from_bytes
from railtracks.llm.encoding import detect_source, ensure_data_uri


def _image_url(source: str) -> str:
    """The ``image_url`` sent for one attachment: URLs as is, everything else a data URL.

    Raises:
        FileNotFoundError: If a local path does not exist.
        ValueError: If the attachment is not an image, or not a path, URL or data URI.
    """
    match detect_source(source):
        case "url":
            return source
        case "data_uri":
            data_uri = ensure_data_uri(source)
        case "local":
            path = Path(source.removeprefix("file://"))
            if not path.is_file():
                raise FileNotFoundError(f"Attachment not found: {source}")
            data = path.read_bytes()
            mime = detect_attachment_mime_from_bytes(data)
            if mime is None or not mime.startswith("image/"):
                raise ValueError(
                    f"Attachment {source!r} is not a supported image "
                    "(PNG, JPEG, GIF or WebP)."
                )
            return f"data:{mime};base64,{base64.b64encode(data).decode('ascii')}"
    if not data_uri.startswith("data:image/"):
        raise ValueError("Decision attachments must be images, got a PDF data URI.")
    return data_uri


def _recorded(source: str) -> str:
    """How an attachment appears in the session record: never its base64 payload."""
    if detect_source(source) != "data_uri":
        return source
    return ensure_data_uri(source).split(",", 1)[0] + ",..."


class DecisionState:
    """Text plus image attachments, for models that accept images (OpenAI's).

    ::

        DecisionState(text="Which animal is this?", attachments="images/cat.jpg")

    Each attachment is a local path, an http(s) URL or a data URI (or bare base64).
    Local files and base64 are sent as data URLs; URLs are sent as is for the provider
    to fetch. Files are read when the state is created, so a bad path fails here.
    System One vendors (TypeSafe, OpenRouter) accept text only and reject attachments
    with a ``DecisionProviderRequestError`` before any request is sent.
    """

    def __init__(
        self,
        text: str | None = None,
        *,
        attachments: str | Sequence[str] | None = None,
    ) -> None:
        """Create a state.

        Args:
            text: The text to judge, if any.
            attachments: One image or a list of images: paths, URLs or data URIs.

        Raises:
            ValueError: If there is neither text nor an attachment, or an attachment
                is not an image.
            FileNotFoundError: If a local attachment does not exist.
        """
        if text is not None and not isinstance(text, str):
            raise TypeError(f"text must be a string, got {type(text).__name__}.")
        sources = [attachments] if isinstance(attachments, str) else attachments or []
        if not all(isinstance(s, str) for s in sources):
            raise TypeError("attachments must be a string or a list of strings.")
        if not text and not sources:
            raise ValueError("A DecisionState needs text, an attachment, or both.")
        self.text = text
        self.attachments: tuple[str, ...] = tuple(sources)
        self.image_urls: tuple[str, ...] = tuple(_image_url(s) for s in sources)

    def to_input(self) -> str | list[dict[str, Any]]:
        """The OpenAI-shape ``input``: plain text, or one user message with parts."""
        if not self.image_urls:
            return self.text or ""
        parts: list[dict[str, Any]] = []
        if self.text:
            parts.append({"type": "input_text", "text": self.text})
        parts += [{"type": "input_image", "image_url": url} for url in self.image_urls]
        return [{"role": "user", "content": parts}]

    def encode(self) -> dict[str, Any]:
        """Plain JSON for the session record: the attachments as given, minus base64."""
        return {
            "text": self.text,
            "attachments": [_recorded(source) for source in self.attachments],
        }

    def __str__(self) -> str:
        names = ", ".join(self.encode()["attachments"])
        return f"{self.text or ''} [{names}]" if names else self.text or ""

    def __repr__(self) -> str:
        return f"DecisionState(text={self.text!r}, attachments={len(self.attachments)})"


DecisionInput: TypeAlias = Union[str, dict[str, Any], list[Any], DecisionState]
"""What a decision is about: text, a JSON object or array, or a ``DecisionState``."""
