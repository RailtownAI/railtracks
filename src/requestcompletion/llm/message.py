from enum import Enum
from typing import Literal, Generic, TypeVar

from .content import Content, ToolResponse



_T = TypeVar("_T", bound=Content)


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

    def __init__(self, content: _T, role: Literal["assistant", "user", "system", "tool"]):
        """
        A simple class that represents a message that an LLM can read.

        Args:
            content: The content of the message. It can take on any of the following types:
                - str: A simple string message.
                - List[ToolCall]: A list of tool calls.
                - ToolResponse: A tool response.
                - BaseModel: A custom base model object.
            role: The role of the message (assistant, user, system, tool, etc.).
        """
        self.validate_content(content)
        self._content = content
        self._role = Role(role)

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

    def __str__(self):
        return f"{self.role}: {self.content}"

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


class UserMessage(_StringOnlyContent):
    """
    A simple class that represents a user message.

    Note that we only support string input
    """

    def __init__(self, content: str):
        super().__init__(content=content, role="user")


class SystemMessage(_StringOnlyContent):
    """
    A simple class that represents a system message.
    """

    def __init__(self, content: str):
        super().__init__(content=content, role="system")


class AssistantMessage(Message[_T], Generic[_T]):
    """
    A simple class that represents a message from the assistant.
    """

    def __init__(self, content: _T):
        super().__init__(content=content, role="assistant")


# TODO further constrict the possible return type of a ToolMessage.
class ToolMessage(Message[ToolResponse]):
    """
    A simple class that represents a message that is a tool call answer.
    """

    def __init__(self, content: ToolResponse):
        super().__init__(content=str(content.result), role="tool")
        self.identifier = content.identifier
