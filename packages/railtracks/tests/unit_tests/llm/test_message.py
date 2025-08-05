import pytest
from typing import List
from railtracks.llm import UserMessage, SystemMessage, AssistantMessage, ToolMessage
from railtracks.llm.content import ToolResponse, ToolCall


# =================================== START Message Structure Tests ==================================
@pytest.mark.parametrize(
    "content, role, expected_str, expected_repr",
    [
        ("Hello", "user", "user: Hello", "user: Hello"),
        ("System message", "system", "system: System message", "system: System message"),
        ("Assistant response", "assistant", "assistant: Assistant response", "assistant: Assistant response"),
    ],
)
def test_message_str_and_repr(content, role, expected_str, expected_repr):
    if role == "user":
        message = UserMessage(content)
    elif role == "system":
        message = SystemMessage(content)
    elif role == "assistant":
        message = AssistantMessage(content)
    else:
        pytest.fail("Invalid role provided for test")

    assert str(message) == expected_str
    assert repr(message) == expected_repr


def test_system_message():
    message = SystemMessage("System message")
    assert message.content == "System message"
    assert message.role == "system"
    assert str(message) == "system: System message"
    assert repr(message) == "system: System message"


def test_assistant_message():
    message = AssistantMessage("Assistant response")
    assert message.content == "Assistant response"
    assert message.role == "assistant"
    assert str(message) == "assistant: Assistant response"
    assert repr(message) == "assistant: Assistant response"


def test_tool_message():
    tool_response = ToolResponse(name="tool1", result="result", identifier="123")
    message = ToolMessage(tool_response)
    assert message.content == tool_response
    assert message.role == "tool"
    assert str(message) == f"tool: {tool_response}"
    assert repr(message) == f"tool: {tool_response}"
    assert message.content.name == "tool1"
    assert message.content.result == "result"
    assert message.content.identifier == "123"


@pytest.mark.parametrize(
    "invalid_content, expected_exception",
    [
        (123, TypeError),
        (None, TypeError),
        (["list", "of", "strings"], TypeError),
    ],
)
def test_invalid_user_message_content(invalid_content, expected_exception):
    with pytest.raises(expected_exception):
        UserMessage(invalid_content)


@pytest.mark.parametrize(
    "invalid_content, expected_exception",
    [
        (123, TypeError),
        (None, TypeError),
        (["list", "of", "strings"], TypeError),
    ],
)
def test_invalid_system_message_content(invalid_content, expected_exception):
    with pytest.raises(expected_exception):
        SystemMessage(invalid_content)


def test_tool_message_invalid_content():
    with pytest.raises(TypeError):
        ToolMessage("Invalid content")  # ToolMessage expects ToolResponse, not str


def test_tool_message_invalid_content2():
    with pytest.raises(TypeError):
        ToolMessage(
            List[
                ToolCall(identifier="123", name="tool1", arguments={}),
                ToolCall(identifier="456", name="tool2", arguments={}),
            ]
        )  # ToolMessage expects ToolResponse, not List[ToolCall]

# =================================== END Message Structure Tests ==================================