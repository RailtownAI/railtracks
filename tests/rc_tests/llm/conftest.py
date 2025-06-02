from typing import List, Callable
import pytest
import src.requestcompletion.llm as llm
from pydantic import BaseModel
from src.requestcompletion.llm import MessageHistory, Tool, AssistantMessage, UserMessage
from src.requestcompletion.llm.response import Response
from src.requestcompletion.llm.history import MessageHistory

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
    

@pytest.fixture
def mock_llm() -> MockLLM:
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
