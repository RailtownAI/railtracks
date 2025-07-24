import pytest
from pydantic import BaseModel, Field
from railtracks.llm.message import UserMessage, AssistantMessage, ToolMessage
from railtracks.llm.history import MessageHistory
from railtracks.llm.content import ToolCall, ToolResponse
from railtracks.llm.tools import Tool, Parameter
from railtracks.llm.models._litellm_wrapper import LiteLLMWrapper


# ====================================== START Tool Fixtures ======================================
@pytest.fixture
def tool():
    """
    Fixture to provide a valid Tool instance.
    """
    return Tool(
        name="example_tool",
        detail="This is an example tool.",
        parameters={
            Parameter(
                name="param1", param_type="string", description="A string parameter."
            ),
            Parameter(
                name="param2", param_type="integer", description="An integer parameter."
            ),
        },
    )


@pytest.fixture
def tool_with_parameters_set():
    """
    Fixture to provide a Tool instance with Parameter objects.
    """
    return Tool(
        name="example_tool",
        detail="This is an example tool with parameters.",
        parameters={
            Parameter(
                name="param1",
                param_type="string",
                description="A string parameter.",
                required=True,
            ),
            Parameter(
                name="param2",
                param_type="integer",
                description="An integer parameter.",
                required=False,
            ),
        },
    )

# ====================================== END Tool Fixtures ======================================

# ====================================== START Message Fixtures ======================================
@pytest.fixture
def user_message():
    """
    Fixture to provide a UserMessage instance.
    """
    return UserMessage(content="This is a user message.")


@pytest.fixture
def assistant_message():
    """
    Fixture to provide an AssistantMessage instance.
    """
    return AssistantMessage(content="This is an assistant message.")


@pytest.fixture
def tool_message(tool_response):
    """
    Fixture to provide a ToolMessage instance.
    """
    return ToolMessage(content=tool_response)


@pytest.fixture
def tool_response():
    """
    Fixture to provide a ToolResponse instance.
    """
    return ToolResponse(identifier="123", name="example_tool", result="success")


@pytest.fixture
def tool_call():
    """
    Fixture to provide a ToolCall instance.
    """
    return ToolCall(identifier="123", name="example_tool", arguments={"arg1": "value1"})

@pytest.fixture
def message_history(user_message, assistant_message):
    """
    Fixture to provide a MessageHistory instance.
    """
    return MessageHistory([user_message, assistant_message])
# ====================================== END Message Fixtures ======================================

# ======================================= START Mock LiteLLMWrapper ======================================
class MockLiteLLMWrapper(LiteLLMWrapper):
    """
    Mock implementation of LiteLLMWrapper for testing purposes.
    """
    @classmethod
    def model_type(cls) -> str:
        return "mock"

    def _invoke(self, messages, *args, **kwargs):
        return {
            "choices": [
                {
                    "message": {"content": "Mocked response"},
                    "finish_reason": "stop",
                }
            ]
        }


@pytest.fixture
def mock_litellm_wrapper():
    """
    Fixture to provide a mock LiteLLMWrapper instance.
    """
    return MockLiteLLMWrapper
# ======================================= END Mock LiteLLMWrapper ======================================
