from abc import ABC

from ._base import OutputLessToolCallLLM

from requestcompletion.llm.message import AssistantMessage


class ToolCallLLM(OutputLessToolCallLLM[AssistantMessage], ABC):
    def return_output(self):
        """Returns the last message in the message history"""
        return self.message_hist[-1]
