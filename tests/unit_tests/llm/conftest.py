from typing import List, Callable, Type
import pytest
from pydantic import BaseModel
import railtracks.llm as llm
from railtracks.llm import MessageHistory, Tool, AssistantMessage, UserMessage
from railtracks.llm.response import Response
from railtracks.llm.history import MessageHistory

# ====================================== Message History ======================================
@pytest.fixture
def message_history() -> MessageHistory:
    """
    Fixture to provide a MessageHistory instance for testing.
    """
    return MessageHistory()
# ====================================== End Message History ==================================

# ====================================== MockLLM ======================================
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
#===================================== END MockLLM ======================================


# ====================================== START Responses ======================================
@pytest.fixture
def assistant_response():
    """
    Fixture to provide a Response object with an AssistantMessage.
    """
    message = AssistantMessage("Hello, I am an assistant.")
    return Response(message)


@pytest.fixture
def user_response():
    """
    Fixture to provide a Response object with a UserMessage.
    """
    message = UserMessage("This is a user message.")
    return Response(message)

# ====================================== END Responses ======================================
