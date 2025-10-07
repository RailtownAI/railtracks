from typing import Generic, TypeVar

from pydantic import BaseModel

from railtracks.llm import MessageHistory, ToolCall, ToolResponse
from railtracks.llm.content import Content
from railtracks.llm.message import Role

_T = TypeVar("_T", bound=Content)


class LLMResponse(Generic[_T]):
    """
    A special response object designed to be returned by an LLM node in the RT system.

    Args:
        content: The content of the response, which can be any content of a message
        message_history: The history of messages exchanged during the interaction.
    """

    def __init__(self, content: _T, message_history: MessageHistory):
        self.content = content
        self.message_history = message_history

    def __repr__(self):
        return f"LLMResponse({self.content})"

    @property
    def tool_invocations(self) -> list[tuple[ToolCall, ToolResponse]]:
        """Returns the text content of the response."""
        self._tool_invocations = []

        for idx, msg in enumerate(self.message_history):
            if msg.role == Role.assistant and isinstance(msg.content, list):
                for tr_idx, tc in enumerate(msg.content):
                    self._tool_invocations.append(
                        (tc, self.message_history[idx + tr_idx + 1].content)
                    )

        return self._tool_invocations


_TStructured = TypeVar("_TStructured", bound=BaseModel)


class StructuredResponse(LLMResponse[_TStructured]):
    """
    A specialized response object for structured outputs from LLMs.

    Args:
        model: The structured model that defines the content of the response.
        message_history: The history of messages exchanged during the interaction.
    """

    def __init__(
        self,
        content: _TStructured,
        message_history: MessageHistory,
    ):
        super().__init__(content, message_history)

    @property
    def structured(self) -> _TStructured:
        """Returns the structured content of the response."""
        if isinstance(self.content, BaseModel):
            return self.content
        else:
            raise TypeError("Unexpected content type")


class StringResponse(LLMResponse[str]):
    """
    A specialized response object for string outputs from LLMs.

    Args:
        content: The string content of the response.
        message_history: The history of messages exchanged during the interaction.
    """

    def __init__(self, content: str, message_history: MessageHistory):
        super().__init__(content, message_history)

    @property
    def text(self) -> str:
        """Returns the text content of the response."""
        if isinstance(self.content, str):
            return self.content
        else:
            raise TypeError("Unexpected content type")
