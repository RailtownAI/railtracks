from typing import List, Callable

import requestcompletion.llm as llm
from pydantic import BaseModel
from requestcompletion.llm import MessageHistory, Tool
from requestcompletion.llm.response import Response


class MockLLM(llm.ModelBase):
    def __init__(
        self,
        chat: Callable[[MessageHistory], Response] = lambda x: Response(),
        structured: Callable[[MessageHistory, BaseModel], Response] = lambda x,
        y: Response(),
        stream_chat: Callable[[MessageHistory], Response] = lambda x: Response(),
        chat_with_tools: Callable[[MessageHistory, List[Tool]], Response] = lambda x,
        y: Response(),
    ):
        self._chat = chat
        self._structured = structured
        self._stream_chat = stream_chat
        self._chat_with_tools = chat_with_tools

    def chat(self, messages: MessageHistory, **kwargs) -> Response:
        return self._chat(messages)

    def structured(
        self, messages: MessageHistory, schema: BaseModel, **kwargs
    ) -> Response:
        return self._structured(messages, schema)

    def stream_chat(self, messages: MessageHistory, **kwargs) -> Response:
        return self._stream_chat(messages)

    def chat_with_tools(
        self, messages: MessageHistory, tools: List[Tool], **kwargs
    ) -> Response:
        return self._chat_with_tools(messages, tools)
