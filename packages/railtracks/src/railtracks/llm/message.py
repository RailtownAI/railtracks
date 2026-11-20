from __future__ import annotations

import base64
import hashlib
import os
import warnings
from collections.abc import Sequence
from copy import deepcopy
from enum import Enum
from typing import Any, Generic, Literal, TypeVar, Union, cast, overload
from urllib import error as urllib_error
from urllib.parse import urlparse

from .attachment_formats import (
    UNSUPPORTED_URL_EXTENSIONS,
    detect_mime,
    detect_mime_from_extension,
)
from .content import Content, ToolCall, ToolCalls, ToolResponse
from .context_injection_utils import ValueDict, fill_template
from .encoding import (
    DEFAULT_MAX_DOWNLOAD_MB,
    MIME_TYPE,
    AttachmentSource,
    decode_base64_attachment,
    decode_data_uri,
    detect_path_source,
    detect_source,
    load_bytes,
    open_url,
    read_file,
    redact_url,
    validate_max_mb,
)

_T = TypeVar("_T", bound=Content)

Modality = Literal["image", "audio", "video", "document", "file"]
"""What an attachment holds. `document` is a PDF; `file` is any other non-media type."""

# Image types most providers accept; other image paths raise until #1703 adds per-model checks.
_PATH_IMAGE_TYPES = frozenset(
    ("image/png", "image/jpeg", "image/gif", "image/webp", "image/avif")
)

_BYTES_LIKE = (bytes, bytearray, memoryview)


def _modality_for_mime(mime_type: str) -> Modality:
    if mime_type == "application/pdf":
        return "document"
    match mime_type.split("/", 1)[0]:
        case "image" | "audio" | "video" as media:
            return media
        case _:
            return "file"


def _validate_mime_type(mime_type: str) -> str:
    """Return `mime_type` lowercased, or raise a `ValueError` unless it is a bare `type/subtype`."""
    normalized = mime_type.strip().lower()
    if not MIME_TYPE.fullmatch(normalized):
        raise ValueError(
            f"mime_type must be a bare 'type/subtype' such as 'image/png', got {mime_type!r}."
        )
    return normalized


def _probe_url_metadata(url: str, *, timeout: float) -> tuple[str | None, str | None]:
    """HEAD-probe a URL and return (content_type, filename) or (None, None) on failure.

    Used when a URL has no recognized extension (e.g. arxiv.org/pdf/1706.03762
    serves a PDF but has no `.pdf` suffix). content_type is lowercase with no
    parameters; filename comes from Content-Disposition, RFC 2231 decoded.
    """
    try:
        with open_url(url, timeout=timeout, method="HEAD") as resp:
            headers = resp.headers
            # get_content_type() reports text/plain for a missing, empty or malformed
            # header; a missing one gives None here, and text/* is ignored downstream.
            content_type = (
                headers.get_content_type() if "Content-Type" in headers else None
            )
            # With both filename= and filename*=, get_filename() returns the plain one,
            # which servers send as an ASCII fallback for the same name.
            return content_type, headers.get_filename()
    except (urllib_error.URLError, OSError, ValueError):
        return None, None


class Attachment:
    """A file attached to a message: an image, audio, video, PDF or other file.

    Build one from a path, URL or base64 payload with `Attachment(...)`, from raw
    bytes with `Attachment.from_bytes`, or from a URL whose type you already know
    with `Attachment.from_url`. Local files and inline payloads are read once and
    kept as raw bytes; the base64 a provider needs is built from them on each send.

    For files and bytes, the MIME type comes from an explicit `mime_type`, then
    the content's magic bytes, then the file extension. Paths, URLs and base64
    strings must hold an image, PDF, audio or video; other files need
    `from_bytes` or `from_url` with an explicit `mime_type`. Attachments are
    read-only, and two are equal when they hold the same bytes (or, for a URL
    that is not fetched, the same URL) and MIME type.
    """

    def __init__(
        self,
        url: str,
        trust_urls: bool = False,
        attachment_timeout: float = 10.0,
        attachment_max_mb: float = DEFAULT_MAX_DOWNLOAD_MB,
    ):
        """
        Create an attachment from a file path, URL, or base64/data-URI payload.

        Args:
            url: A file path, URL, or base64/data-URI payload.
            trust_urls: Allow in-process network I/O for URL attachments. When
                False (default), `.pdf` URLs raise instead of being downloaded,
                and URLs with no recognized extension are passed through to the
                provider as an `image_url` without a HEAD probe. Set True to
                enable both (a) HEAD-probing URLs without an image or PDF
                extension and (b) downloading PDF URLs into the prompt. Only safe
                for developer-controlled URLs; end-user-supplied URLs are an SSRF
                surface once their bytes are fetched in-process. It does not
                cover downloads litellm makes itself for some providers.
            attachment_timeout: Per-request timeout in seconds for the HEAD
                probe and the in-process PDF download. Defaults to 10. Only
                applies when `trust_urls=True`.
            attachment_max_mb: Largest PDF accepted from a URL, in megabytes.
                Must be positive and finite. Defaults to 32. Only applies when
                `trust_urls=True`.

        Raises:
            TypeError: If `url` is not a string.
            FileNotFoundError: If a local file does not exist.
            ValueError: If `attachment_max_mb` is not positive and finite, `url`
                has a scheme other than http(s), ftp(s) or `file:` (such as
                `s3://`), a local file is empty, a local file or base64 payload is not an
                image, PDF, audio or video file, a local image is not PNG, JPEG,
                GIF, WebP or AVIF, a data URI or base64 payload is malformed, a
                URL's extension names a text or Office document type, or a PDF
                URL is passed while `trust_urls` is False.
        """
        if not isinstance(url, str):
            raise TypeError(
                f"The url parameter must be a string representing a file path or URL, but got {type(url)}"
            )
        validate_max_mb(attachment_max_mb, name="attachment_max_mb")

        inline = (
            decode_data_uri(url)
            if url.startswith("data:")
            else decode_base64_attachment(url)
        )
        if inline is not None:
            mime_type, data = inline
            self._set("...", "data_uri", mime_type, None, data)
        elif detect_path_source(url) == "url":
            self._init_url(
                url,
                mime_type=None,
                filename=None,
                trust_urls=trust_urls,
                timeout=attachment_timeout,
                max_mb=attachment_max_mb,
            )
        else:
            data = read_file(url)
            self._set(url, "local", detect_mime(data, url), os.path.basename(url), data)

        if self._type != "url" and (self._mime_type is None or self.modality == "file"):
            source = url if self._type == "local" else "base64 data"
            raise ValueError(
                f"Unsupported attachment format: {self._mime_type or 'unknown type'} "
                f"in {source!r}. Paths and base64 strings must be an image, PDF, "
                "audio or video file; use Attachment.from_bytes with an explicit "
                "mime_type for other files."
            )
        if (
            self._type == "local"
            and self.modality == "image"
            and self._mime_type not in _PATH_IMAGE_TYPES
        ):
            raise ValueError(
                f"Unsupported attachment format: {self._mime_type} in {url!r}. "
                "Image paths must be PNG, JPEG, GIF, WebP or AVIF, the formats most "
                "providers accept; use Attachment.from_bytes with an explicit "
                "mime_type to send another image type."
            )

    @classmethod
    def from_bytes(
        cls,
        data: bytes | bytearray | memoryview,
        mime_type: str | None = None,
        filename: str | None = None,
    ) -> Attachment:
        """Create an attachment from raw bytes, of any file type.

        Args:
            data: The file content.
            mime_type: The MIME type, e.g. `"audio/wav"`. Detected from the magic
                bytes, then from `filename`'s extension, when omitted.
            filename: The file name sent to providers that take one.

        Returns:
            The attachment, with `type` `"data_uri"`.

        Raises:
            TypeError: If `data` is not bytes-like.
            ValueError: If `data` is empty, `mime_type` is not a bare
                `type/subtype`, or `mime_type` is omitted and cannot be detected.
        """
        if not isinstance(data, (bytes, bytearray, memoryview)):
            raise TypeError(f"data must be bytes, but got {type(data)}")
        data = bytes(data)
        if mime_type is not None:
            mime_type = _validate_mime_type(mime_type)
        else:
            mime_type = detect_mime(data, filename)
            if mime_type is None:
                raise ValueError(
                    "Cannot detect the attachment's MIME type from its bytes"
                    f"{' or file name' if filename else ''}; pass mime_type."
                )
        attachment = cls.__new__(cls)
        attachment._set("...", "data_uri", mime_type, filename, data)
        return attachment

    @classmethod
    def from_url(
        cls,
        url: str,
        mime_type: str | None = None,
        filename: str | None = None,
        trust_urls: bool = False,
        attachment_timeout: float = 10.0,
        attachment_max_mb: float = DEFAULT_MAX_DOWNLOAD_MB,
    ) -> Attachment:
        """Create an attachment from a URL, optionally declaring its type.

        Image, audio and video URLs are passed to the provider as they are. A PDF
        is downloaded in-process (capped at `attachment_max_mb`), and only with
        `trust_urls=True`, as for `Attachment(url)`.

        Args:
            url: An `http`, `https`, `ftp` or `ftps` URL.
            mime_type: The MIME type. Skips the extension check and the HEAD
                probe, which helps for URLs without an extension.
            filename: The file name sent to providers that take one. Defaults to
                the last segment of the URL path.
            trust_urls: Allow in-process network I/O for this URL. See
                `Attachment.__init__`.
            attachment_timeout: Per-request timeout in seconds for the HEAD
                probe and the PDF download.
            attachment_max_mb: Largest PDF accepted, in megabytes. Must be
                positive and finite.

        Returns:
            The attachment, with `type` `"url"`.

        Raises:
            ValueError: If `url` is not a URL, `mime_type` is not a bare
                `type/subtype`, `attachment_max_mb` is not positive and finite,
                the URL's extension names a text or Office document type and no
                `mime_type` is given, or the attachment is a PDF and `trust_urls`
                is False.
        """
        if detect_source(url) != "url":
            raise ValueError(f"Not a URL: {url!r}")
        validate_max_mb(attachment_max_mb, name="attachment_max_mb")
        attachment = cls.__new__(cls)
        attachment._init_url(
            url,
            mime_type=_validate_mime_type(mime_type) if mime_type is not None else None,
            filename=filename,
            trust_urls=trust_urls,
            timeout=attachment_timeout,
            max_mb=attachment_max_mb,
        )
        return attachment

    def _init_url(
        self,
        url: str,
        *,
        mime_type: str | None,
        filename: str | None,
        trust_urls: bool,
        timeout: float,
        max_mb: float,
    ) -> None:
        url_path = urlparse(url).path
        extension_mime = detect_mime_from_extension(url_path)
        # Image and PDF extensions are trusted. Audio and video ones are a fallback,
        # since a video path can serve a thumbnail; `.php` or `.pl` say nothing.
        extension_modality = (
            _modality_for_mime(extension_mime) if extension_mime else None
        )
        probed_filename: str | None = None
        if mime_type is None and extension_modality in ("image", "document"):
            mime_type = extension_mime
        if mime_type is None and trust_urls:
            # The server knows best for a URL without an image or PDF extension
            # (e.g. https://arxiv.org/pdf/1706.03762). Skipped unless trusted, so
            # unknown URLs are never touched from the railtracks process.
            probed_type, probed_filename = _probe_url_metadata(url, timeout=timeout)
            if probed_type and _modality_for_mime(probed_type) != "file":
                mime_type = probed_type
        if mime_type is None and extension_modality in ("audio", "video"):
            mime_type = extension_mime
        if mime_type is None:
            extension = os.path.splitext(url_path)[1].lower()
            if extension in UNSUPPORTED_URL_EXTENSIONS:
                raise ValueError(
                    f"Unsupported attachment format: {extension} in URL {redact_url(url)!r}. "
                    "URL attachments must be an image, PDF, audio or video file."
                )
        data: bytes | None = None
        # Provider file blocks need the bytes; other URLs are sent as they are.
        if mime_type is not None and _modality_for_mime(mime_type) == "document":
            if not trust_urls:
                raise ValueError(
                    f"PDF URL attachments require trust_urls=True: {redact_url(url)!r}. "
                    "Constructing this attachment would fetch the URL in-process and "
                    "embed its bytes into the LLM prompt, which is an SSRF/exfiltration "
                    "surface for end-user-supplied URLs. Pass trust_urls=True only "
                    "when the URL is developer-controlled; otherwise download the PDF "
                    "first and pass a local file path or base64/data-URI payload."
                )
            data = load_bytes(url, timeout=timeout, max_mb=max_mb)
        self._set(
            url,
            "url",
            mime_type,
            filename or probed_filename or os.path.basename(url_path) or None,
            data,
        )

    def _set(
        self,
        url: str,
        source: AttachmentSource,
        mime_type: str | None,
        filename: str | None,
        data: bytes | None,
    ) -> None:
        if data is not None and not data:
            name = filename or (url if source != "data_uri" else None)
            raise ValueError(
                f"Attachment {name!r} is empty."
                if name
                else "Attachment data is empty."
            )
        self._url = url
        self._type: AttachmentSource = source
        self._mime_type = mime_type
        self._filename = filename or None
        self._data = data
        self._sha256: str | None = None

    @property
    def url(self) -> str:
        """The path or URL given, or `"..."` for inline data."""
        return self._url

    @property
    def type(self) -> AttachmentSource:
        """Where the attachment came from: `"local"`, `"url"` or `"data_uri"` (any inline data)."""
        return self._type

    @property
    def mime_type(self) -> str | None:
        """The MIME type, or None for a URL whose type is unknown."""
        return self._mime_type

    @property
    def filename(self) -> str | None:
        """The file name, when one is known."""
        return self._filename

    @property
    def size(self) -> int | None:
        """The size in bytes, or None when only the URL is held."""
        return None if self._data is None else len(self._data)

    @property
    def sha256(self) -> str | None:
        """Hex SHA-256 of the bytes, the same for every source, or None when only the URL is held."""
        if self._sha256 is None and self._data is not None:
            self._sha256 = hashlib.sha256(self._data).hexdigest()
        return self._sha256

    @property
    def modality(self) -> Modality:
        """What the attachment holds, from its MIME type; a URL of unknown type counts as an image."""
        if self._mime_type is None:
            return "image"
        return _modality_for_mime(self._mime_type)

    @property
    def file_extension(self) -> None:
        """Always None. Deprecated: read `filename` or `mime_type` instead."""
        warnings.warn(
            "Attachment.file_extension is always None and will be removed; "
            "read filename or mime_type instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        return None

    @property
    def data(self) -> bytes | None:
        """The raw bytes, or None for a URL that is passed to the provider as is."""
        return self._data

    @property
    def base64(self) -> str | None:
        """The bytes as plain base64, built on each read, or None when only the URL is held."""
        if self._data is None:
            return None
        return base64.b64encode(self._data).decode("ascii")

    @property
    def encoding(self) -> str | None:
        """The bytes as a base64 data URI, built on each read, or None when only the URL is held."""
        payload = self.base64
        if payload is None:
            return None
        return f"data:{self.mime_type};base64,{payload}"

    def _identity(self) -> tuple[str, str | None]:
        return (self.sha256 or self.url, self.mime_type)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Attachment):
            return NotImplemented
        return self._identity() == other._identity()

    def __hash__(self) -> int:
        return hash(self._identity())

    # Read-only, so copies (histories are deep-copied on every model call) can share it.
    def __copy__(self) -> Attachment:
        return self

    def __deepcopy__(self, memo: dict[int, Any]) -> Attachment:
        return self

    def __repr__(self) -> str:
        fields = [f"type={self.type!r}", f"mime_type={self.mime_type!r}"]
        if self.type == "url":
            fields.append(f"url={redact_url(self.url)!r}")
        if self.filename is not None:
            fields.append(f"filename={self.filename!r}")
        if self.size is not None:
            fields.append(f"size={self.size}")
        return f"Attachment({', '.join(fields)})"


AttachmentInput = str | Attachment | bytes | bytearray | memoryview


def _as_attachment(
    item: AttachmentInput,
    *,
    trust_urls: bool,
    attachment_timeout: float,
    attachment_max_mb: float,
) -> Attachment:
    """Return `item` as an `Attachment`, building one from a source string or raw bytes."""
    if isinstance(item, Attachment):
        return item
    if isinstance(item, _BYTES_LIKE):
        return Attachment.from_bytes(item)
    return Attachment(
        item,
        trust_urls=trust_urls,
        attachment_timeout=attachment_timeout,
        attachment_max_mb=attachment_max_mb,
    )


ContentPart = Union[str, Attachment, ToolCall]
"""One part of a message's content: text, an attachment, or a tool call (assistant only)."""

_PART_TYPES = (str, Attachment, ToolCall)

# Joins text parts in `.text`, so separate parts never run into one word.
_TEXT_SEPARATOR = "\n"


def _to_parts(
    content: object, *, owner: str, allowed: tuple[type, ...] = (str, Attachment)
) -> list[ContentPart]:
    """Return `content` (one part, or a sequence of parts) as a new list of parts.

    Args:
        content: The content given to a message.
        owner: The message class, named in errors.
        allowed: The part types this message accepts.

    Raises:
        TypeError: If `content` or one of its items is not one of `allowed`.
    """
    names = [kind.__name__ for kind in allowed]
    expected = (
        names[0] if len(names) == 1 else f"{', '.join(names[:-1])} or {names[-1]}"
    )
    if isinstance(content, allowed):
        return [cast(ContentPart, content)]
    if isinstance(content, Sequence) and not isinstance(content, (str, *_BYTES_LIKE)):
        parts = list(content)
        for part in parts:
            if not isinstance(part, allowed):
                hint = (
                    " Wrap raw bytes with Attachment.from_bytes."
                    if Attachment in allowed and isinstance(part, _BYTES_LIKE)
                    else ""
                )
                raise TypeError(
                    f"{owner} content parts must be {expected}, but got "
                    f"{type(part).__name__}.{hint}"
                )
        return parts
    raise TypeError(
        f"{owner} content must be {expected}, or a list of them, but got "
        f"{type(content).__name__}."
    )


def _parts_of(content: object) -> list[ContentPart] | None:
    """Return `content` as parts when it is text or a list of parts, else None."""
    if isinstance(content, str):
        return [content]
    if isinstance(content, list) and all(
        isinstance(part, _PART_TYPES) for part in content
    ):
        return cast(list[ContentPart], content)
    return None


def _render_parts(parts: list[ContentPart]) -> str:
    """Render parts one per line: text as is, tool calls as `name(arguments)`, attachments by repr."""
    return _TEXT_SEPARATOR.join(
        repr(part) if isinstance(part, Attachment) else str(part) for part in parts
    )


def content_text(content: object) -> str:
    """Return the text in a message's content.

    Args:
        content: A message's `content`.

    Returns:
        The text parts joined with newlines, or `""` for content with no text, such as
        structured output.
    """
    parts = _parts_of(content) or []
    return _TEXT_SEPARATOR.join(part for part in parts if isinstance(part, str))


def content_attachments(content: object) -> list[Attachment]:
    """Return the attachments in a message's content, in order, or `[]` when it has none."""
    parts = _parts_of(content) or []
    return [part for part in parts if isinstance(part, Attachment)]


def encode_content(content: object) -> object:
    """Encode a message's content for the session record.

    Text-only content becomes its text, and empty content (a reply with no content)
    becomes None. Content with tool calls becomes the list of calls; the text spoken
    with them is recorded separately by `AssistantMessage.encode`. Content with
    attachments becomes one text part followed by one `{"modality", "type", "info"}`
    part per attachment. Other content, such as structured output, is returned as it is.

    Args:
        content: A message's `content`.

    Returns:
        The encoded content.
    """
    parts = _parts_of(content)
    if parts is None:
        return content
    if not parts:
        return None
    tool_calls = [part for part in parts if isinstance(part, ToolCall)]
    if tool_calls:
        return tool_calls
    attachments = content_attachments(content)
    if not attachments:
        return content_text(content)
    return [
        {"type": "text", "text": content_text(content)},
        *(
            {"modality": item.modality, "type": item.type, "info": item.url}
            for item in attachments
        ),
    ]


class Role(str, Enum):
    """
    A simple enum type that can be used to represent the role of a message.

    Note this role is not often used and you should use the literals instead.
    """

    assistant = "assistant"
    user = "user"
    system = "system"
    tool = "tool"


_TRole = TypeVar("_TRole", bound=Role)


class Message(Generic[_T, _TRole]):
    """
    A base class that represents a message that an LLM can read.

    Note the content may take on a variety of allowable types.
    """

    def __init__(
        self,
        content: _T,
        role: _TRole,
    ):
        """
        A simple class that represents a message that an LLM can read.

        Args:
            content: The content of the message. It can take on any of the following types:
                - list[ContentPart]: Text, attachments and tool calls, in order.
                - str: Plain text, from a custom model.
                - BaseModel: Structured output.
            role: The role of the message (assistant, user, system, tool, etc.).
        """
        assert isinstance(role, Role)
        self.validate_content(content)
        self._content = content
        self._role = role

    @classmethod
    def validate_content(cls, content: _T):
        pass

    @property
    def content(self) -> _T:
        """Collects the content of the message."""
        return self._content

    @property
    def role(self) -> _TRole:
        """Collects the role of the message."""
        return self._role

    @property
    def text(self) -> str:
        """The text parts of the message's content, joined with newlines. Empty for structured output."""
        return content_text(self._content)

    @property
    def attachments(self) -> list[Attachment]:
        """The attachments in the message's content, in order."""
        return content_attachments(self._content)

    def __str__(self):
        parts = _parts_of(self.content)
        if parts is None or isinstance(self.content, str):
            return f"{self.role.value}: {self.content}"
        return f"{self.role.value}: {_render_parts(parts)}"

    def __repr__(self):
        return str(self)

    def encode(self) -> dict[str, Any]:
        return {
            "role": self.role.value,
            "content": encode_content(self.content),
        }

    @property
    def tool_calls(self) -> list[ToolCall]:
        """Copies of the tool calls in the message's content, in order; empty when there are none."""
        parts = _parts_of(self.content) or []
        return [deepcopy(part) for part in parts if isinstance(part, ToolCall)]


class _PromptMessage(Message[list[ContentPart], _TRole], Generic[_TRole]):
    """A message whose text parts are prompt templates (user and system messages)."""

    def fill_prompt(self, value_dict: ValueDict) -> None:
        """Fill `{key}` placeholders in the text parts, leaving attachments in place."""
        self._content = [
            fill_template(part, value_dict) if isinstance(part, str) else part
            for part in self._content
        ]


class UserMessage(_PromptMessage[Role.user]):
    """
    A message from the user: text and attachments, in order.

    `content` is always a list of parts, so `UserMessage("Hi").content == ["Hi"]`.
    Read `text` for the text and `attachments` for the attachments.

    Args:
        content: The text, an `Attachment`, or a list of text and `Attachment`s in
                    the order the model should read them, e.g.
                    `["Before:", Attachment("a.png"), "After:", Attachment("b.png")]`.
        attachment: Attachment(s) placed after `content`: a file path, URL,
                    data URI, raw bytes or `Attachment`, or a list of them.
                    Raw bytes go through `Attachment.from_bytes`. Defaults to None.
        trust_urls: Allow in-process fetch for URL attachments. Defaults to False.
                    When False, `.pdf` URLs and URLs whose extension names a
                    text or Office document type raise, and other
                    URLs without an image, PDF, audio or video extension are
                    handed to the provider unprobed (as `image_url`). When True,
                    `.pdf` URLs are downloaded and embedded as base64, and every
                    other URL without an image or PDF extension is HEAD-probed;
                    an image, PDF, audio or video type it reports wins.
                    Set True only when every URL in `attachment` is
                    developer-controlled — end-user-supplied URLs are an SSRF
                    surface once their bytes are fetched in-process.
                    `trust_urls`, `attachment_timeout` and `attachment_max_mb`
                    do not apply to `Attachment` objects, which are already built.
        attachment_timeout: Per-request timeout in seconds for the HEAD probe
                    and the in-process PDF download. Defaults to 10. Only
                    applies when `trust_urls=True`. Raise this for large PDFs
                    over slow links.
        attachment_max_mb: Largest PDF accepted from a URL, in megabytes.
                    Must be positive and finite. Defaults to 32. Only applies
                    when `trust_urls=True`.

    Raises:
        TypeError: If a part of `content` is neither a `str` nor an `Attachment`.
        ValueError: If the message has no parts, or an attachment is rejected for
            the reasons listed on `Attachment.__init__` and `Attachment.from_bytes`.
    """

    def __init__(
        self,
        content: str | Attachment | Sequence[ContentPart] | None = None,
        attachment: AttachmentInput | Sequence[AttachmentInput] | None = None,
        trust_urls: bool = False,
        attachment_timeout: float = 10.0,
        attachment_max_mb: float = DEFAULT_MAX_DOWNLOAD_MB,
    ):
        parts = [] if content is None else _to_parts(content, owner="UserMessage")
        if attachment is not None:
            items = (
                [attachment]
                if isinstance(attachment, (str, Attachment, *_BYTES_LIKE))
                else list(attachment)
            )
            parts.extend(
                _as_attachment(
                    item,
                    trust_urls=trust_urls,
                    attachment_timeout=attachment_timeout,
                    attachment_max_mb=attachment_max_mb,
                )
                for item in items
            )
        if not parts:
            raise ValueError("UserMessage needs text or at least one attachment.")
        super().__init__(content=parts, role=Role.user)

    @property
    def attachment(self) -> list[Attachment] | None:
        """The attachments, or None when there are none. Deprecated: read `attachments` instead."""
        warnings.warn(
            "UserMessage.attachment is deprecated and will be removed; "
            "read UserMessage.attachments instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        return self.attachments or None


class SystemMessage(_PromptMessage[Role.system]):
    """
    The instructions for the model.

    `content` is a list of text parts, so `SystemMessage("Be brief.").content == ["Be brief."]`.
    Read `text` for the instructions as one string.

    Args:
        content: The text, or a list of text parts.

    Raises:
        TypeError: If a part is not a `str`; system messages take no attachments.
    """

    def __init__(self, content: str | Sequence[str]):
        super().__init__(
            content=_to_parts(content, owner="SystemMessage", allowed=(str,)),
            role=Role.system,
        )


def _assistant_content(content: object) -> object:
    """Normalize an assistant message's content: a list of parts, or structured output."""
    if content is None:
        return []
    if isinstance(content, ToolCalls):
        return [content.text, *content] if content.text else list(content)
    # Before the BaseModel check: a ToolCall is a pydantic model, not structured output.
    if isinstance(content, (str, Attachment, ToolCall, list, tuple)):
        return _to_parts(content, owner="AssistantMessage", allowed=_PART_TYPES)
    return content


class AssistantMessage(Message[_T, Role.assistant], Generic[_T]):
    """
    A simple class that represents a message from the assistant.

    Args:
        content: The content of the assistant message: a list of text, attachments and
            tool calls, in the order the model produced them, such as
            `["Let me check.", ToolCall(...)]`. A single part or None (no content) is
            normalized to a list, so `AssistantMessage("Hi").content == ["Hi"]`.
            Structured output is the pydantic model itself. Read `tool_calls` to find a
            tool-calling turn.
    """

    @overload
    def __init__(
        self: AssistantMessage[list[ContentPart]],
        content: str | Attachment | ToolCall | Sequence[ContentPart] | None,
    ) -> None: ...

    @overload
    def __init__(self, content: _T) -> None: ...

    def __init__(self, content: object):
        super().__init__(
            content=cast(_T, _assistant_content(content)), role=Role.assistant
        )

        # Metadata that lives outside `content`. Any attribute added below must also
        # be copied in `copy_metadata_from`, or rebuild paths will silently drop it.
        #
        # Optionally stores the raw litellm message object so providers that
        # attach extra metadata (e.g. Gemini thought_signature) can round-trip
        # it back without any manual reconstruction.
        self.raw_litellm_message: Any | None = None

        # Reasoning/"thinking" the model surfaced alongside its answer, when the
        # provider returns it (Anthropic, DeepSeek, Gemini, OpenAI in part).
        self.reasoning_content: str | None = None  # human-readable text
        self.thinking_blocks: list[dict[str, Any]] | None = None

    def copy_metadata_from(self, other: Message) -> "AssistantMessage":
        """Copy the provider metadata that lives outside `content` from `other`.

        Rebuild paths (e.g. the tool loop, which must deep-copy `tool_calls`) construct a
        fresh message from `content` alone; this carries over everything else so the
        rebuild stays lossless. New metadata attributes must be added here. Read with
        `getattr` so a plain `Message` source (which lacks these) is a no-op. Returns self
        for chaining.
        """
        self.raw_litellm_message = getattr(other, "raw_litellm_message", None)
        self.reasoning_content = getattr(other, "reasoning_content", None)
        self.thinking_blocks = getattr(other, "thinking_blocks", None)
        return self

    def encode(self):
        encoded = super().encode()

        # A tool-calling turn encodes as the array of calls; the text spoken with them
        # goes beside it, the way providers put it on the wire.
        if self.tool_calls and self.text:
            encoded["text"] = self.text

        # Surface reasoning in the serialized message so it is visible in the run
        # graph/session data, not just on the live object.
        if self.reasoning_content is not None:
            encoded["reasoning_content"] = self.reasoning_content
        if self.thinking_blocks is not None:
            encoded["thinking_blocks"] = self.thinking_blocks

        return encoded


class ToolMessage(Message[list[ContentPart], Role.tool]):
    """
    A tool's answer to one tool call.

    `content` is a list of text and attachments, like a user message, so
    `ToolMessage("18°C", tool_call_id="c1", name="get_weather").content == ["18°C"]`.

    Args:
        content: The tool's result: text, an `Attachment`, or a list of both.
        tool_call_id: The `identifier` of the `ToolCall` this answers.
        name: The name of the tool that ran.

    Raises:
        TypeError: If a part of `content` is neither a `str` nor an `Attachment`, or
            `tool_call_id` or `name` is missing.
    """

    def __init__(
        self,
        content: str | Attachment | Sequence[str | Attachment] | ToolResponse,
        tool_call_id: str | None = None,
        name: str | None = None,
    ):
        if isinstance(content, ToolResponse):
            warnings.warn(
                "ToolMessage(ToolResponse(...)) is deprecated and will be removed; use "
                "ToolMessage(result, tool_call_id=..., name=...) instead.",
                DeprecationWarning,
                stacklevel=2,
            )
            tool_call_id, name = content.identifier, content.name
            result = content.result
            content = (
                result if isinstance(result, str) else result.decode("utf-8", "replace")
            )
        if tool_call_id is None or name is None:
            raise TypeError("ToolMessage needs tool_call_id and name.")
        super().__init__(
            content=_to_parts(content, owner="ToolMessage"), role=Role.tool
        )
        self.tool_call_id = tool_call_id
        self.name = name

    @property
    def identifier(self) -> str:
        """The tool call's identifier. Deprecated: read `tool_call_id` instead."""
        warnings.warn(
            "ToolMessage.identifier is deprecated and will be removed; "
            "read ToolMessage.tool_call_id instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        return self.tool_call_id

    @property
    def result(self) -> str:
        """The tool's text result. Deprecated: read `text` instead."""
        warnings.warn(
            "ToolMessage.result is deprecated and will be removed; "
            "read ToolMessage.text instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        return self.text

    def __str__(self):
        return f"{self.role.value}: {self.name} -> {_render_parts(self.content)}"

    def encode(self) -> dict[str, Any]:
        return {
            "role": self.role.value,
            "content": {
                "identifier": self.tool_call_id,
                "name": self.name,
                "result": encode_content(self.content),
            },
        }
