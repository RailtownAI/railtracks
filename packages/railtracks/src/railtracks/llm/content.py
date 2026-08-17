from __future__ import annotations

from typing import (
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
    An assistant turn that calls tools: the calls themselves, plus any text the
    model spoke alongside them.

    Models routinely answer with both at once — "I'll look that up for you."
    followed by a call to `search`. Holding that text here rather than in a
    separate field on the message keeps the model's whole response inside
    `content`.

    This is a `list[ToolCall]`, so anything that already treats tool-call
    content as a list — iteration, indexing, `isinstance(content, list)` —
    keeps working, and `AssistantMessage` accepts a plain list as before.
    """

    def __init__(
        self, tool_calls: Iterable[ToolCall] = (), text: str | None = None
    ) -> None:
        super().__init__(tool_calls)
        self.text = text

    def __repr__(self):
        if self.text is None:
            return f"ToolCalls({list.__repr__(self)})"
        return f"ToolCalls({list.__repr__(self)}, text={self.text!r})"


class ToolResponse(BaseModel):
    """
    A simple model object that represents a tool response.

    This simple model should be used when adding a response to a tool.
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


# ToolCalls is a List[ToolCall] subclass, so it is already covered by the
# List[ToolCall] member; it is named here because it is the shape an assistant
# tool-calling turn actually takes.
Content = Union[str, ToolCalls, List[ToolCall], ToolResponse, BaseModel]
