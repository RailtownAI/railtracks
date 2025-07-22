from abc import ABC

from railtracks.llm import MessageHistory, SystemMessage

from ._base import OutputLessToolCallLLM


class MessageHistoryToolCallLLM(OutputLessToolCallLLM[MessageHistory], ABC):
    def return_output(self) -> MessageHistory:
        return MessageHistory(
            [x for x in self.message_hist if x.role is not SystemMessage]
        )
