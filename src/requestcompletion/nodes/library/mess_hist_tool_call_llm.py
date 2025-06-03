from ._tool_call_llm_base import OutputLessToolCallLLM
from ...llm import MessageHistory

from abc import ABC


class MessageHistoryToolCallLLM(OutputLessToolCallLLM[MessageHistory], ABC):
    def return_output(self) -> MessageHistory:
        return self.message_hist
