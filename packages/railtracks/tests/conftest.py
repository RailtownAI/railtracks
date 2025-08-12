from typing import Callable, List, Type

import pytest

from railtracks.llm import MessageHistory, Tool
from railtracks.llm.response import Response
import railtracks.llm as llm

from pydantic import BaseModel

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
        super().__init__()
        self._chat = chat
        self._structured = structured
        self._stream_chat = stream_chat
        self._chat_with_tools = chat_with_tools

    def _chat(self, messages: MessageHistory, **kwargs) -> Response:
        return self._chat(messages)

    def _structured(self, messages: MessageHistory, schema: BaseModel, **kwargs) -> Response:
        return self._structured(messages, schema)

    def _stream_chat(self, messages: MessageHistory, **kwargs) -> Response:
        return self._stream_chat(messages)

    def _chat_with_tools(self, messages: MessageHistory, tools: List[Tool], **kwargs) -> Response:
        return self._chat_with_tools(messages, tools)

    async def _achat(self, messages: MessageHistory, **kwargs) -> Response:
        return self._chat(messages)

    async def _astructured(
            self, messages: MessageHistory, schema: BaseModel, **kwargs
    ) -> Response:
        return self._structured(messages, schema)

    async def _astream_chat(self, messages: MessageHistory, **kwargs) -> Response:
        return self._stream_chat(messages)

    async def _achat_with_tools(
            self, messages: MessageHistory, tools: List[Tool], **kwargs
    ) -> Response:
        return self._chat_with_tools(messages, tools)

    def model_name(self) -> str | None:
        return "MockLLM"

    @classmethod
    def model_type(cls) -> str | None:
        return "mock"


@pytest.fixture
def mock_llm() -> Type[MockLLM]:
    return MockLLM