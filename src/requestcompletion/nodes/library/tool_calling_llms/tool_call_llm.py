from ._base import OutputLessToolCallLLM

from abc import ABC


class ToolCallLLM(OutputLessToolCallLLM[str], ABC):
    def return_output(self):
        """Returns the last message in the message history"""
        return self.message_hist[-1].content
