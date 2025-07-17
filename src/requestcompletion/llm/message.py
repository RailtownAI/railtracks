from enum import Enum
from typing import Generic, Literal, TypeVar

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


class UserMessage(_StringOnlyContent):
    """
    Note that we only support string input

    Args:
        content (str): The content of the user message.
        inject_prompt (bool, optional): Whether to inject prompt with context variables. Defaults to True.
    """

    def __init__(self, content: str, inject_prompt: bool = True):
        super().__init__(content=content, role="user", inject_prompt=inject_prompt)


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
