from __future__ import annotations

import warnings
from typing import (
    TYPE_CHECKING,
    Any,
    AnyStr,
    Dict,
    Generator,
    Generic,
    Iterable,
    List,
    TypeVar,
    Union,
)

from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from .message import ContentPart


####################################################################################################
# Simple helper Data Structures for common responses #
####################################################################################################
class ToolCall(BaseModel):
    """
    A simple model object that represents a tool call.

    This simple model represents a moment when a tool is called.
    """

    identifier: str = Field(description="The identifier attatched to this tool call.")
    name: str = Field(description="The name of the tool being called.")
    arguments: Dict[str, Any] = Field(
        description="The arguments provided as input to the tool."
    )

    def __str__(self):
        return f"{self.name}({self.arguments})"


class ToolCalls(List[ToolCall]):
    """
    Deprecated: put tool calls in the message content instead, as
    `AssistantMessage(["Let me check.", ToolCall(...)])`.

    An `AssistantMessage` given a `ToolCalls` stores its text and calls as content
    parts, and `message.tool_calls` lists the calls of any message.
    """

    def __init__(
        self, tool_calls: Iterable[ToolCall] = (), text: str | None = None
    ) -> None:
        warnings.warn(
            "ToolCalls is deprecated and will be removed; put the calls in the message "
            "content, as AssistantMessage([text, *calls]), and read message.tool_calls.",
            DeprecationWarning,
            stacklevel=2,
        )
        super().__init__(tool_calls)
        self.text = text

    def __repr__(self):
        if self.text is None:
            return f"ToolCalls({list.__repr__(self)})"
        return f"ToolCalls({list.__repr__(self)}, text={self.text!r})"


class ToolResponse(BaseModel):
    """
    Deprecated: build `ToolMessage(result, tool_call_id=..., name=...)` instead.

    `ToolMessage(ToolResponse(...))` still works and is converted to that form.
    """

    identifier: str = Field(
        description="The identifier attached to this tool response. This should match the identifier of the tool call."
    )
    name: str = Field(description="The name of the tool that generated this response.")
    result: AnyStr = Field(description="The result of the tool call.")

    def __str__(self):
        return f"{self.name} -> {self.result}"


_TOutput = TypeVar("_TOutput", str, BaseModel)


class Stream(Generic[_TOutput]):
    """
    A simple object that represents a streaming response from a model.

    This simple model is used to represent a streaming response from a model.
    It contains a streamer attribute that is a generator that yields strings.
    """

    def __init__(
        self,
        streamer: Generator[str, None, None],
        final_message: _TOutput | None = None,
    ):
        """
        Creates a new instance of a Stream object.

        Args:
            streamer: A generator that streams the response as a collection of chunked Response objects.
            final_message: The final message or data structure obtained after the streaming ends.
        """
        if streamer is not None and not isinstance(streamer, Generator):
            raise TypeError(
                f"streamer must be of type Generator/ AsyncGenerator, got {type(streamer)}"
            )
        self._streamer = streamer
        self._final_message = final_message

    @property
    def final_message(self):
        """
        Gets the final message that was constructed from the streamer, after the streamer has finished.
        """
        return self._final_message

    @final_message.setter
    def final_message(self, value: _TOutput):
        self._final_message = value

    @property
    def streamer(self):
        """
        Gets the streamer that was returned as part of this response.
        """
        return self._streamer

    def __str__(self):
        return f"Stream(streamer={self._streamer})"

    def __repr__(self):
        return f"Stream(streamer={self._streamer})"


Content = Union["List[ContentPart]", str, BaseModel]
