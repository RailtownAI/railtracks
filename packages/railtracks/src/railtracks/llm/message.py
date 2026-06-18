from __future__ import annotations

import logging
import os
import re
from copy import deepcopy
from enum import Enum
from typing import Generic, TypeVar
from urllib import error as urllib_error
from urllib import request as urllib_request
from urllib.parse import urlparse

from .content import Content, ToolCall, ToolResponse
from .encoding import detect_source, encode, ensure_data_uri
from .prompt_injection_utils import KeyOnlyFormatter, ValueDict

logger = logging.getLogger(__name__)

_T = TypeVar("_T", bound=Content)


_EXTENSION_MIME_MAP = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".gif": "image/gif",
    ".webp": "image/webp",
    ".pdf": "application/pdf",
}


def _modality_for_mime(mime_type: str) -> str:
    if mime_type == "application/pdf":
        return "document"
    return "image"


def _probe_url_metadata(url: str) -> tuple[str | None, str | None]:
    """HEAD-probe a URL and return (content_type, filename) or (None, None) on failure.

    Used when a URL has no recognized extension (e.g. arxiv.org/pdf/1706.03762
    serves a PDF but has no `.pdf` suffix). content_type strips any `; charset=...`
    suffix; filename comes from Content-Disposition if present.
    """
    try:
        req = urllib_request.Request(url, method="HEAD")
        with urllib_request.urlopen(req, timeout=10) as resp:
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
    """
    A simple class that represents an attachment to a message.
    """

    def __init__(self, url: str):
        """
        A simple class that represents an attachment to a message.

        Args:
            url (str): The URL of the attachment.
        """
        self.url = url
        self.file_extension = None
        self.encoding = None
        self.mime_type: str | None = None
        self.modality = "image"
        self.filename: str | None = None

        if not isinstance(url, str):
            raise TypeError(
                f"The url parameter must be a string representing a file path or URL, but got {type(url)}"
            )

        match detect_source(url):
            case "local":
                _, file_extension = os.path.splitext(self.url)
                file_extension = file_extension.lower()
                if file_extension not in _EXTENSION_MIME_MAP:
                    raise ValueError(
                        f"Unsupported attachment format: {file_extension}. Supported formats: {', '.join(_EXTENSION_MIME_MAP.keys())}"
                    )
                self.mime_type = _EXTENSION_MIME_MAP[file_extension]
                self.modality = _modality_for_mime(self.mime_type)
                self.encoding = f"data:{self.mime_type};base64,{encode(url)}"
                self.filename = os.path.basename(url) or None
                self.type = "local"
            case "url":
                url_path = urlparse(self.url).path
                _, file_extension = os.path.splitext(url_path)
                file_extension = file_extension.lower()
                probed_filename: str | None = None
                if file_extension in _EXTENSION_MIME_MAP:
                    self.mime_type = _EXTENSION_MIME_MAP[file_extension]
                else:
                    # No usable extension (e.g. https://arxiv.org/pdf/1706.03762);
                    # HEAD-probe to figure out what we're actually being handed.
                    probed_ct, probed_filename = _probe_url_metadata(self.url)
                    if probed_ct == "application/pdf" or (
                        probed_ct and probed_ct.startswith("image/")
                    ):
                        self.mime_type = probed_ct
                if self.mime_type:
                    self.modality = _modality_for_mime(self.mime_type)
                self.filename = probed_filename or os.path.basename(url_path) or None
                # Provider file blocks need base64; image_url blocks accept the URL as-is.
                if self.modality == "document":
                    self.encoding = f"data:{self.mime_type};base64,{encode(url)}"
                self.type = "url"
            case "data_uri":
                self.url = "..."
                self.encoding = ensure_data_uri(url)  # dynamically add header if needed
                # Parse the header we just produced to populate mime_type / modality
                header = self.encoding.split(",", 1)[0]  # "data:<mime>;base64"
                self.mime_type = header[len("data:") :].split(";", 1)[0]
                self.modality = _modality_for_mime(self.mime_type)
                self.type = "data_uri"


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
        inject_prompt: bool = True,
    ):
        """
        A simple class that represents a message that an LLM can read.

        Args:
            content: The content of the message. It can take on any of the following types:
                - str: A simple string message.
                - List[ToolCall]: A list of tool calls.
                - ToolResponse: A tool response.
                - BaseModel: A custom base model object.
                - Stream: A stream object with a final_message and a generator.
            role: The role of the message (assistant, user, system, tool, etc.).
            inject_prompt (bool, optional): Whether to inject prompt with context variables. Defaults to True.
        """
        assert isinstance(role, Role)
        self.validate_content(content)
        self._content = content
        self._role = role
        self._inject_prompt = inject_prompt

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
    def inject_prompt(self) -> bool:
        """
        A boolean that indicates whether this message should be injected into from context.
        """
        return self._inject_prompt

    @inject_prompt.setter
    def inject_prompt(self, value: bool):
        """
        Sets the inject_prompt property.
        """
        self._inject_prompt = value

    def __str__(self):
        return f"{self.role.value}: {self.content}"

    def __repr__(self):
        return str(self)

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
        self._content = KeyOnlyFormatter().vformat(self._content, (), value_dict)


class UserMessage(_StringOnlyContent[Role.user]):
    """
    Note that we only support string input

    Args:
        content: The content of the user message.
        attachment: The file attachment(s) for the user message. Can be a single string or a list of strings,
                    containing file paths, URLs, or data URIs. Defaults to None.
        inject_prompt: Whether to inject prompt with context variables. Defaults to True.
    """

    def __init__(
        self,
        content: str | None = None,
        attachment: str | list[str] | None = None,
        inject_prompt: bool = True,
    ):
        if attachment is not None:
            if isinstance(attachment, list):
                self.attachment = [Attachment(att) for att in attachment]
            else:
                self.attachment = [Attachment(attachment)]

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
        super().__init__(content=content, role=Role.user, inject_prompt=inject_prompt)


class SystemMessage(_StringOnlyContent[Role.system]):
    """
    A simple class that represents a system message.

    Args:
        content (str): The content of the system message.
        inject_prompt (bool, optional): Whether to inject prompt with context  variables. Defaults to True.
    """

    def __init__(self, content: str, inject_prompt: bool = True):
        super().__init__(content=content, role=Role.system, inject_prompt=inject_prompt)


class AssistantMessage(Message[_T, Role.assistant], Generic[_T]):
    """
    A simple class that represents a message from the assistant.

    Args:
        content (_T): The content of the assistant message.
        inject_prompt (bool, optional): Whether to inject prompt with context  variables. Defaults to True.
    """

    def __init__(self, content: _T, inject_prompt: bool = True):
        super().__init__(
            content=content, role=Role.assistant, inject_prompt=inject_prompt
        )

        # Optionally stores the raw litellm message object so providers that
        # attach extra metadata (e.g. Gemini thought_signature) can round-trip
        # it back without any manual reconstruction.
        self.raw_litellm_message = None


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
