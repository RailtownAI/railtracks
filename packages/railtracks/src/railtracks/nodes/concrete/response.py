from typing import Generic, TypeVar

from pydantic import BaseModel

from railtracks.llm import MessageHistory
from railtracks.llm.content import Content

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


_TBaseModel = TypeVar("_TBaseModel", bound=BaseModel)


class StructuredResponse(LLMResponse[_TBaseModel]):
    """
    A specialized response object for structured outputs from LLMs.

    Args:
        model: The structured model that defines the content of the response.
        message_history: The history of messages exchanged during the interaction.
    """

    def __init__(self, model: _TBaseModel, message_history: MessageHistory):
        super().__init__(model, message_history)

    @property
    def structured(self) -> _TBaseModel:
        """Returns the structured content of the response."""
        return self.content


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
        return self.content
