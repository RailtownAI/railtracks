from typing import Generic, TypeVar, Generator

from pydantic import BaseModel

from railtracks.llm import MessageHistory
from railtracks.llm.content import Content, Stream

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


class StringResponse(LLMResponse[str | Stream]):
    """
    A specialized response object for string outputs from LLMs.

    Args:
        content: The string content of the response.
        message_history: The history of messages exchanged during the interaction.
    """

    def __init__(self, content: str | Stream, message_history: MessageHistory):
        super().__init__(content, message_history)

    @property
    def text(self) -> str:
        """Returns the text content of the response."""
        if isinstance(self.content, str):
            return self.content
        elif isinstance(self.content, Stream):
            return self.content.final_message
        else:
            raise ValueError("Unexpected content type")
    
    @property
    def streamer(self) -> Generator[str, None, None]:
        """Returns the streamer that was returned as part of this response.
        
        Note that this is a generator that yields strings.
        """ 
        assert isinstance(self.content, Stream), "For this property to be usable, the llm should have stream=True"
        return self.content.streamer