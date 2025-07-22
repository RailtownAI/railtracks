from abc import ABC

from requestcompletion.llm.message import AssistantMessage

from ._base import OutputLessToolCallLLM


class ToolCallLLM(OutputLessToolCallLLM[AssistantMessage], ABC):
    def return_output(self):
        """Returns the last message in the message history"""
        return self.message_hist[-1]
