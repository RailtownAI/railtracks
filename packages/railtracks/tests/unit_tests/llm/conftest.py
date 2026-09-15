import pytest
from railtracks.llm import AssistantMessage, MessageHistory, UserMessage
from railtracks.llm.response import Response


# ====================================== Message History ======================================
@pytest.fixture
def message_history() -> MessageHistory:
    """
    Fixture to provide a MessageHistory instance for testing.
    """
    return MessageHistory()


# ====================================== End Message History ==================================


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
