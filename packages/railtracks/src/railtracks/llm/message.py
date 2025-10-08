import os
from enum import Enum
from typing import Generic, Literal, TypeVar

from .content import Content, ToolResponse
from .multimodal import detect_source, encode
from .prompt_injection_utils import KeyOnlyFormatter, ValueDict

_T = TypeVar("_T", bound=Content)


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
        self.modality = "image"  # we currently only support image attachments but this could be extended in the future

        if not isinstance(url, str):
            raise TypeError(
                f"The url parameter must be a string representing a file path or URL, but got {type(url)}"
            )

        match detect_source(url):
            case "local":
                _, file_extension = os.path.splitext(self.url)
                file_extension = file_extension.lower()
                mime_type_map = {
                    ".jpg": "jpeg",
                    ".jpeg": "jpeg",
                    ".png": "png",
                    ".gif": "gif",
                    ".webp": "webp",
                }
                if file_extension not in mime_type_map:
                    raise ValueError(
                        f"Unsupported attachment format: {file_extension}. Supported formats: {', '.join(mime_type_map.keys())}"
                    )
                self.encoding = f"data:{self.modality}/{mime_type_map[file_extension]};base64,{encode(url)}"
                self.type = "local"
            case "url":
                self.url = url
                self.type = "url"
            case "data_uri":
                self.url = "..."  # if the user provides a data uri we just use it as is
                self.encoding = url
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


class Message(Generic[_T]):
    """
    A base class that represents a message that an LLM can read.

    Note the content may take on a variety of allowable types.
    """

    def __init__(
        self,
        content: _T,
        role: Literal["assistant", "user", "system", "tool"],
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
            role: The role of the message (assistant, user, system, tool, etc.).
            inject_prompt (bool, optional): Whether to inject prompt with context variables. Defaults to True.
        """
        self.validate_content(content)
        self._content = content
        self._role = Role(role)
        self._inject_prompt = inject_prompt

    @classmethod
    def validate_content(cls, content: _T):
        pass

    @property
    def content(self) -> _T:
        """Collects the content of the message."""
        return self._content

    @property
    def role(self) -> Role:
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


class _StringOnlyContent(Message[str]):
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


class UserMessage(_StringOnlyContent):
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
        content: str,
        attachment: str | list[str] | None = None,
        inject_prompt: bool = True,
    ):
        super().__init__(content=content, role="user", inject_prompt=inject_prompt)

        if attachment is not None:
            if isinstance(attachment, list):
                self.attachment = [Attachment(att) for att in attachment]
            else:
                self.attachment = [Attachment(attachment)]
        else:
            self.attachment = None

        # self.image_url = image_url

        # if self.image_url is not None:
        #     if not isinstance(image_url, str):
        #         raise TypeError(f"The image parameter must be a string representing a file path or URL, but got {type(image_url)}")

        #     try:
        #         match detect_image_source(image_url):
        #             case "local":
        #                 encoded_image = encode_image(image_url)
        #                 _, file_extension = os.path.splitext(image_url)
        #                 file_extension = file_extension.lower()  # Normalize to lowercase

        #                 # Map file extensions to MIME types
        #                 mime_type_map = {
        #                     ".jpg": "jpeg",
        #                     ".jpeg": "jpeg",
        #                     ".png": "png",
        #                     ".gif": "gif",
        #                     ".webp": "webp"
        #                 }

        #                 if file_extension in mime_type_map:
        #                     mime_type = mime_type_map[file_extension]
        #                     self.image_url = f"data:image/{mime_type};base64,{encoded_image}"
        #                 else:
        #                     raise ValueError(f"Unsupported image format: {file_extension}. Supported formats: {', '.join(mime_type_map.keys())}")
        #             case "url":
        #                 self.image_url = image_url
        #             case "data_uri":
        #                 # Already a data URI, use as-is
        #                 self.image_url = image_url

        #     except Exception as e:
        #         raise ValueError(f"Failed to process image: {e}")


class SystemMessage(_StringOnlyContent):
    """
    A simple class that represents a system message.

    Args:
        content (str): The content of the system message.
        inject_prompt (bool, optional): Whether to inject prompt with context  variables. Defaults to True.
    """

    def __init__(self, content: str, inject_prompt: bool = True):
        super().__init__(content=content, role="system", inject_prompt=inject_prompt)


class AssistantMessage(Message[_T], Generic[_T]):
    """
    A simple class that represents a message from the assistant.

    Args:
        content (_T): The content of the assistant message.
        inject_prompt (bool, optional): Whether to inject prompt with context  variables. Defaults to True.
    """

    def __init__(self, content: _T, inject_prompt: bool = True):
        super().__init__(content=content, role="assistant", inject_prompt=inject_prompt)


# TODO further constrict the possible return type of a ToolMessage.
class ToolMessage(Message[ToolResponse]):
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
        super().__init__(content=content, role="tool")
