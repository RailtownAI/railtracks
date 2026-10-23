from __future__ import annotations

import base64
import hashlib
import logging
import os
import re
from collections.abc import Sequence
from copy import deepcopy
from enum import Enum
from typing import Any, Generic, Literal, TypeVar, cast
from urllib import error as urllib_error
from urllib import request as urllib_request
from urllib.parse import urlparse

from .attachment_formats import (
    detect_attachment_mime_from_bytes,
    detect_mime_from_extension,
)
from .content import Content, ToolCall, ToolCalls, ToolResponse
from .context_injection_utils import ValueDict, fill_template
from .encoding import (
    DEFAULT_MAX_DOWNLOAD_MB,
    decode_data_uri,
    detect_source,
    load_bytes,
    validate_max_mb,
)

logger = logging.getLogger(__name__)

_T = TypeVar("_T", bound=Content)

Modality = Literal["image", "audio", "video", "document", "file"]
"""What an attachment holds. `document` is a PDF; `file` is any other non-media type."""

AttachmentSource = Literal["local", "url", "data_uri"]
"""Where an attachment came from; `data_uri` covers every inline payload, raw bytes included."""

_MEDIA_MODALITIES: dict[str, Modality] = {
    "image": "image",
    "audio": "audio",
    "video": "video",
}

# URLs ending in these raise: providers cannot take them as attachments by URL.
_UNSUPPORTED_URL_EXTENSIONS = frozenset(
    (".csv", ".htm", ".html", ".md", ".txt")  # text
    + (".doc", ".docx", ".ppt", ".pptx", ".xls", ".xlsx")  # Office
)


def _modality_for_mime(mime_type: str) -> Modality:
    if mime_type == "application/pdf":
        return "document"
    return _MEDIA_MODALITIES.get(mime_type.split("/", 1)[0], "file")


def _probe_url_metadata(url: str, *, timeout: float) -> tuple[str | None, str | None]:
    """HEAD-probe a URL and return (content_type, filename) or (None, None) on failure.

    Used when a URL has no recognized extension (e.g. arxiv.org/pdf/1706.03762
    serves a PDF but has no `.pdf` suffix). content_type strips any `; charset=...`
    suffix; filename comes from Content-Disposition if present.
    """
    try:
        req = urllib_request.Request(url, method="HEAD")
        with urllib_request.urlopen(req, timeout=timeout) as resp:
            ct = (
                resp.headers.get("Content-Type", "").split(";", 1)[0].strip().lower()
                or None
            )
            cd = resp.headers.get("Content-Disposition", "")
            m = re.search(r'filename\*?=(?:[^\'\"]*\'\')?"?([^";]+)"?', cd)
            fname = m.group(1).strip() if m else None
            return ct, fname
    except (urllib_error.URLError, OSError, ValueError):
        return None, None


class Attachment:
    """A file attached to a message: an image, audio, video, PDF or other file.

    Build one from a path, URL or base64 payload with `Attachment(...)`, from raw
    bytes with `Attachment.from_bytes`, or from a URL whose type you already know
    with `Attachment.from_url`. Local files and inline payloads are read once and
    kept as raw bytes; the base64 a provider needs is built from them on each send.

    The MIME type comes from, in order: an explicit `mime_type`, the content's
    magic bytes, then the file extension. Two attachments are equal when they hold
    the same bytes (or, for a URL that is not fetched, the same URL) and MIME type.

    Attributes:
        url: The path or URL given, or `"..."` for inline data.
        type: Where the attachment came from: `"local"`, `"url"` or `"data_uri"`.
        mime_type: The MIME type, or None for a URL whose type is unknown.
        filename: The file name, when one is known.
        size: The size in bytes, or None when only the URL is held.
        sha256: Hex SHA-256 of the bytes, or None when only the URL is held.
    """

    url: str
    type: AttachmentSource
    mime_type: str | None
    filename: str | None
    size: int | None
    sha256: str | None

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
            ValueError: If `attachment_max_mb` is not positive and finite, a
                local file is empty or its type cannot be detected, a data URI
                or base64 payload is malformed, a URL's extension names a text
                or Office document type, or a PDF URL is passed while
                `trust_urls` is False.
        """
        if not isinstance(url, str):
            raise TypeError(
                f"The url parameter must be a string representing a file path or URL, but got {type(url)}"
            )
        validate_max_mb(attachment_max_mb, name="attachment_max_mb")

        match detect_source(url):
            case "local":
                data = load_bytes(url)
                mime_type = detect_attachment_mime_from_bytes(
                    data
                ) or detect_mime_from_extension(url)
                if mime_type is None:
                    raise ValueError(
                        f"Unsupported attachment format: cannot tell the type of {url!r} "
                        "from its contents or extension. Use Attachment.from_bytes "
                        "with an explicit mime_type."
                    )
                self._set(url, "local", mime_type, os.path.basename(url) or None, data)
            case "url":
                self._init_url(
                    url,
                    mime_type=None,
                    filename=None,
                    trust_urls=trust_urls,
                    timeout=attachment_timeout,
                    max_mb=attachment_max_mb,
                )
            case "data_uri":
                mime_type, data = decode_data_uri(url)
                self._set("...", "data_uri", mime_type, None, data)

    @classmethod
    def from_bytes(
        cls,
        data: bytes,
        mime_type: str | None = None,
        filename: str | None = None,
    ) -> Attachment:
        """Create an attachment from raw bytes.

        Args:
            data: The file content.
            mime_type: The MIME type, e.g. `"audio/wav"`. Detected from the magic
                bytes, then from `filename`'s extension, when omitted.
            filename: The file name sent to providers that take one.

        Returns:
            The attachment, with `type` `"data_uri"`.

        Raises:
            TypeError: If `data` is not bytes.
            ValueError: If `data` is empty, or `mime_type` is omitted and cannot
                be detected.
        """
        if not isinstance(data, bytes):
            raise TypeError(f"data must be bytes, but got {type(data)}")
        if mime_type is None:
            mime_type = detect_attachment_mime_from_bytes(data) or (
                detect_mime_from_extension(filename) if filename else None
            )
            if mime_type is None:
                raise ValueError(
                    "Cannot detect the attachment's MIME type from its bytes"
                    f"{' or file name' if filename else ''}; pass mime_type."
                )
        attachment = cls.__new__(cls)
        attachment._set("...", "data_uri", mime_type.lower(), filename, data)
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
            ValueError: If `url` is not a URL, `attachment_max_mb` is not
                positive and finite, the URL's extension names a text or Office
                document type and no `mime_type` is given, or the attachment is a
                PDF and `trust_urls` is False.
        """
        if detect_source(url) != "url":
            raise ValueError(f"Not a URL: {url!r}")
        validate_max_mb(attachment_max_mb, name="attachment_max_mb")
        attachment = cls.__new__(cls)
        attachment._init_url(
            url,
            mime_type=mime_type.lower() if mime_type else None,
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
        # `.php` or `.pl` can serve an image, so only a media extension is trusted.
        extension_mime = detect_mime_from_extension(url_path)
        if extension_mime and _modality_for_mime(extension_mime) == "file":
            extension_mime = None
        probed_filename: str | None = None
        if mime_type is None and extension_mime is not None:
            if _modality_for_mime(extension_mime) in ("image", "document"):
                mime_type = extension_mime
        if mime_type is None and trust_urls:
            # The server knows best for a URL without an image or PDF extension
            # (e.g. https://arxiv.org/pdf/1706.03762, or a thumbnail served from a
            # video path). Skipped unless trusted, so unknown URLs are never
            # touched from the railtracks process.
            probed_ct, probed_filename = _probe_url_metadata(url, timeout=timeout)
            if probed_ct and _modality_for_mime(probed_ct) != "file":
                mime_type = probed_ct
        mime_type = mime_type or extension_mime
        if mime_type is None:
            extension = os.path.splitext(url_path)[1].lower()
            if extension in _UNSUPPORTED_URL_EXTENSIONS:
                raise ValueError(
                    f"Unsupported attachment format: {extension} in URL {url!r}. "
                    "URL attachments must be an image, PDF, audio or video file."
                )
        data: bytes | None = None
        # Provider file blocks need the bytes; other URLs are sent as they are.
        if mime_type is not None and _modality_for_mime(mime_type) == "document":
            if not trust_urls:
                raise ValueError(
                    f"PDF URL attachments require trust_urls=True: {url!r}. "
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
            raise ValueError(f"Attachment {filename or url!r} is empty.")
        self.url = url
        self.type = source
        self.mime_type = mime_type
        self.filename = filename
        self._data = data
        # Computed here rather than on first read: histories are deep-copied on
        # every model call, and a lazily cached hash would be redone per copy.
        self.size = None if data is None else len(data)
        self.sha256 = None if data is None else hashlib.sha256(data).hexdigest()

    @property
    def modality(self) -> Modality:
        """What the attachment holds, from its MIME type; a URL of unknown type counts as an image."""
        if self.mime_type is None:
            return "image"
        return _modality_for_mime(self.mime_type)

    @property
    def data(self) -> bytes | None:
        """The raw bytes, or None for a URL that is passed to the provider as is."""
        return self._data

    @property
    def encoding(self) -> str | None:
        """The bytes as a base64 data URI, built on each read, or None when only the URL is held."""
        if self._data is None:
            return None
        payload = base64.b64encode(self._data).decode("ascii")
        return f"data:{self.mime_type};base64,{payload}"

    def _identity(self) -> tuple[str, str | None]:
        return (self.sha256 or self.url, self.mime_type)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Attachment):
            return NotImplemented
        return self._identity() == other._identity()

    def __hash__(self) -> int:
        return hash(self._identity())

    def __repr__(self) -> str:
        fields = [f"type={self.type!r}", f"mime_type={self.mime_type!r}"]
        if self.type == "url":
            fields.append(f"url={self.url!r}")
        if self.filename is not None:
            fields.append(f"filename={self.filename!r}")
        if self.size is not None:
            fields.append(f"size={self.size}")
        return f"Attachment({', '.join(fields)})"


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
                - str: A simple string message.
                - ToolCalls: Tool calls plus any text the model spoke alongside them.
                - List[ToolCall]: A list of tool calls.
                - ToolResponse: A tool response.
                - BaseModel: A custom base model object.
                - Stream: A stream object with a final_message and a generator.
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

    def __str__(self):
        return f"{self.role.value}: {self.content}"

    def __repr__(self):
        return str(self)

    def encode(self) -> dict[str, Any]:
        return {
            "role": self.role.value,
            "content": self.content,
        }

    @property
    def tool_calls(self):
        """Gets the tool calls attached to this message, if any. If there are none return and empty list."""
        tools: list[ToolCall] = []
        if isinstance(self.content, list):
            tools.extend(deepcopy(self.content))

        return tools


class _StringOnlyContent(Message[str, _TRole], Generic[_TRole]):
    """
    A helper class used to represent a message that only accepts string content.
    """

    @classmethod
    def validate_content(cls, content: str):
        """
        A method used to validate that the content of the message is a string.
        """
        if not isinstance(content, str):
            raise TypeError(f"A {cls.__name__} needs a string but got {type(content)}")

    def fill_prompt(self, value_dict: ValueDict) -> None:
        self._content = fill_template(self._content, value_dict)


class UserMessage(_StringOnlyContent[Role.user]):
    """
    Note that we only support string input

    Args:
        content: The content of the user message.
        attachment: The file attachment(s) for the user message: a file path, URL,
                    data URI or `Attachment`, or a list of them. Defaults to None.
        trust_urls: Allow in-process fetch for URL attachments. Defaults to False.
                    When False, `.pdf` URLs and URLs whose extension names a
                    text or Office document type raise, and other
                    unknown-extension URLs are handed to the provider unprobed
                    (as `image_url`). When True, `.pdf` URLs are downloaded and
                    embedded as base64, and every other URL without an image
                    or PDF extension is HEAD-probed, and the reported type wins.
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
        ValueError: If an attachment is rejected, for the reasons listed on
            `Attachment.__init__`.
    """

    def __init__(
        self,
        content: str | None = None,
        attachment: str | Attachment | Sequence[str | Attachment] | None = None,
        trust_urls: bool = False,
        attachment_timeout: float = 10.0,
        attachment_max_mb: float = DEFAULT_MAX_DOWNLOAD_MB,
    ):
        if attachment is not None:
            items = (
                [attachment]
                if isinstance(attachment, (str, Attachment))
                else list(attachment)
            )
            self.attachment = [
                item
                if isinstance(item, Attachment)
                else Attachment(
                    item,
                    trust_urls=trust_urls,
                    attachment_timeout=attachment_timeout,
                    attachment_max_mb=attachment_max_mb,
                )
                for item in items
            ]

            if content is None:
                logger.warning(
                    "UserMessage initialized without content, setting to empty string."
                )
                content = ""
        else:
            self.attachment = None

        if content is None:
            raise ValueError(
                "UserMessage must have content if no attachment is provided."
            )
        super().__init__(content=content, role=Role.user)

    def encode(self):
        if self.attachment is not None:
            attachment = [
                {
                    "modality": msg_attachment.modality,
                    "type": msg_attachment.type,
                    "info": msg_attachment.url,
                }
                for msg_attachment in self.attachment
            ]

            return {
                "role": self.role.value,
                "content": [{"type": "text", "text": self.content}, *attachment],
            }

        return super().encode()


class SystemMessage(_StringOnlyContent[Role.system]):
    """
    A simple class that represents a system message.

    Args:
        content (str): The content of the system message.
    """

    def __init__(self, content: str):
        super().__init__(content=content, role=Role.system)


class AssistantMessage(Message[_T, Role.assistant], Generic[_T]):
    """
    A simple class that represents a message from the assistant.

    Args:
        content (_T): The content of the assistant message. A tool-calling turn is a
            `ToolCalls`, which holds both the calls and any text the model spoke
            alongside them; a plain `list[ToolCall]` is accepted and normalized to one.
    """

    def __init__(self, content: _T):
        # Normalizing here means a tool-calling turn is always a ToolCalls, so
        # nothing downstream has to handle both shapes, while callers that pass a
        # plain list of tool calls keep working.
        if isinstance(content, list) and not isinstance(content, ToolCalls):
            content = cast(_T, ToolCalls(content))

        super().__init__(content=content, role=Role.assistant)

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

        # A ToolCalls encodes as a bare array, which would drop the text the model
        # spoke with its calls; surface it the way providers put it on the wire.
        if isinstance(self.content, ToolCalls) and self.content.text is not None:
            encoded["text"] = self.content.text

        # Surface reasoning in the serialized message so it is visible in the run
        # graph/session data, not just on the live object.
        if self.reasoning_content is not None:
            encoded["reasoning_content"] = self.reasoning_content
        if self.thinking_blocks is not None:
            encoded["thinking_blocks"] = self.thinking_blocks

        return encoded


# TODO further constrict the possible return type of a ToolMessage.
class ToolMessage(Message[ToolResponse, Role.tool]):
    """
    A simple class that represents a message that is a tool call answer.

    Args:
        content (ToolResponse): The tool response content for the message.
    """

    def __init__(self, content: ToolResponse):
        if not isinstance(content, ToolResponse):
            raise TypeError(
                f"A {self.__class__.__name__} needs a ToolResponse but got {type(content)}. Check the invoke function of the OutputLessToolCallLLM node. That is the only place to return a ToolMessage."
            )
        super().__init__(content=content, role=Role.tool)
