from abc import ABC

from requestcompletion.llm import MessageHistory

from ._base import OutputLessToolCallLLM


class MessageHistoryToolCallLLM(OutputLessToolCallLLM[MessageHistory], ABC):
    def return_output(self) -> MessageHistory:
        return self.message_hist
