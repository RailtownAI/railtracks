from typing import Any, Generic, TypeVar

from pydantic import BaseModel

from railtracks.llm import MessageHistory, ToolCall, ToolResponse
from railtracks.llm.content import Content
from railtracks.llm.message import Role, warn_content_read

_T = TypeVar("_T", bound=Content)


class LLMResponse(Generic[_T]):
    """
    A special response object designed to be returned by an LLM node in the RT system.

    Args:
        content: The content of the response, which can be any content of a message
        message_history: The history of messages exchanged during the interaction.
    """

    def __init__(self, content: _T, message_history: MessageHistory):
        self._content = content
        self.message_history = message_history

    @property
    def content(self) -> _T:
        """The final reply: its text, or your model for an `output_schema` agent.

        Reading text content from user code emits a `FutureWarning`, since it becomes a
        list of parts in railtracks 1.9.0. Read `.text` instead.
        """
        warn_content_read(type(self).__name__, self._content, ".text")
        return self._content

    @property
    def text(self) -> str:
        """The text of the final reply.

        Raises:
            TypeError: If the response holds structured output; read `structured` instead.
        """
        if isinstance(self._content, BaseModel):
            raise TypeError(
                f"This response holds structured output ({type(self._content).__name__}), "
                "not text. Read `.structured` instead."
            )
        return str(self._content)

    def __repr__(self):
        return f"LLMResponse({self.content})"

    def encode(self) -> dict[str, Any]:
        return {
            "content": self.content,
            "message_history": self.message_history,
        }

    def __str__(self):
        # The content is what consumers (notably a parent agent reading this node's
        # output as a tool result) care about, so it must not carry the class wrapper.
        return str(self.content)

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
