from ._base import OutputLessToolCallLLM
from requestcompletion.llm import MessageHistory

from abc import ABC


class MessageHistoryToolCallLLM(OutputLessToolCallLLM[MessageHistory], ABC):
    def return_output(self) -> MessageHistory:
        return self.message_hist
