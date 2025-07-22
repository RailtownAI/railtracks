from abc import ABC
from typing import Generic, TypeVar

from pydantic import BaseModel

from railtracks.exceptions.errors import LLMError
from railtracks.llm.history import MessageHistory
from railtracks.llm.message import AssistantMessage, SystemMessage
from railtracks.nodes.library.tool_calling_llms._structured_base import (
    OutputLessStructuredToolCallLLM,
)

_TSchema = TypeVar("_TSchema", bound=BaseModel)


class StructuredMessageHistoryToolCallLLM(
    OutputLessStructuredToolCallLLM[MessageHistory, _TSchema], ABC, Generic[_TSchema]
):
    """
    A tool call LLM that returns a structured message history.
    This is used for structured message history tool calls.
    """

    def return_output(self) -> MessageHistory:
        if self.structured_output is None:
            raise LLMError("Structured output is None, an unknown error occurred.")

        if isinstance(self.structured_output, Exception):
            raise self.structured_output from self.structured_output

        # Might need to change the logic so that you keep the unstructured message
        self.message_hist.pop()
        self.message_hist.append(AssistantMessage(content=self.structured_output))
        return MessageHistory(
            [x for x in self.message_hist if x.role is not SystemMessage]
        )
