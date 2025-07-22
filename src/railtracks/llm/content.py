from __future__ import annotations

from typing import Any, AnyStr, Dict, List, Union

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


Content = Union[str, List[ToolCall], ToolResponse, BaseModel]
