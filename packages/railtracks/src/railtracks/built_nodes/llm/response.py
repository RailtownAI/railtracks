from typing import Any, Generic, Sequence, TypeVar

from pydantic import BaseModel

from railtracks.llm import MessageHistory, ToolCall, ToolCalls, ToolResponse
from railtracks.llm.content import Content
from railtracks.llm.message import (
    Attachment,
    ContentPart,
    Role,
    content_attachments,
    content_text,
    encode_content,
)

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

    @property
    def text(self) -> str:
        """The text of the response: its text parts joined with newlines.

        Raises:
            TypeError: If the response holds structured output; read `structured` instead.
        """
        if isinstance(self.content, BaseModel):
            raise TypeError(
                f"This response holds structured output ({type(self.content).__name__}), "
                "not text. Read `.structured` instead."
            )
        return content_text(self.content)

    @property
    def attachments(self) -> list[Attachment]:
        """The attachments in the response, in order."""
        return content_attachments(self.content)

    def __repr__(self):
        return f"LLMResponse({self.content})"

    def encode(self) -> dict[str, Any]:
        return {
            "content": encode_content(self.content),
            "message_history": self.message_history,
        }

    def __str__(self):
        # The content is what consumers (notably a parent agent reading this node's
        # output as a tool result) care about, so it must not carry the class wrapper.
        if isinstance(self.content, list):
            return content_text(self.content)
        return str(self.content)

    @property
    def tool_invocations(self) -> list[tuple[ToolCall, ToolResponse]]:
        """Returns each tool call in the history paired with its response."""
        self._tool_invocations = []

        for idx, msg in enumerate(self.message_history):
            if msg.role == Role.assistant and isinstance(msg.content, ToolCalls):
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


class StringResponse(LLMResponse[list[ContentPart]]):
    """
    A response object for text outputs from LLMs.

    `content` is the reply as a list of text and attachments; read `text` for the text.

    Args:
        content: The reply: a `str`, or a list of text and attachments.
        message_history: The history of messages exchanged during the interaction.
    """

    def __init__(
        self, content: str | Sequence[ContentPart], message_history: MessageHistory
    ):
        parts: list[ContentPart] = (
            [content] if isinstance(content, str) else list(content)
        )
        super().__init__(parts, message_history)
