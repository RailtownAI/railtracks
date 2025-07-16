from abc import ABC

from ._base import OutputLessToolCallLLM


class ToolCallLLM(OutputLessToolCallLLM[str], ABC):
    def return_output(self):
        """Returns the last message in the message history"""
        return self.message_hist[-1]
