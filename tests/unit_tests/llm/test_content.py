import pytest
from railtracks.llm.content import ToolCall, ToolResponse


def test_tool_call_str():
    tool_call = ToolCall(identifier="123", name="example_tool", arguments={"arg1": "value1", "arg2": "value2"})
    assert str(tool_call) == "example_tool({'arg1': 'value1', 'arg2': 'value2'})"


def test_tool_response_str():
    tool_response = ToolResponse(identifier="123", name="example_tool", result="success")
    assert str(tool_response) == "example_tool -> success"


@pytest.mark.parametrize(
    "invalid_identifier, invalid_name, invalid_arguments, expected_exception",
    [
        (None, "example_tool", {"arg1": "value1"}, ValueError),
        ("123", None, {"arg1": "value1"}, ValueError),
        ("123", "example_tool", None, ValueError),
    ],
)
def test_invalid_tool_call(invalid_identifier, invalid_name, invalid_arguments, expected_exception):
    with pytest.raises(expected_exception):
        ToolCall(identifier=invalid_identifier, name=invalid_name, arguments=invalid_arguments)


@pytest.mark.parametrize(
    "invalid_identifier, invalid_name, invalid_result, expected_exception",
    [
        (None, "example_tool", "success", ValueError),
        ("123", None, "success", ValueError),
        ("123", "example_tool", None, ValueError),
    ],
)
def test_invalid_tool_response(invalid_identifier, invalid_name, invalid_result, expected_exception):
    with pytest.raises(expected_exception):
        ToolResponse(identifier=invalid_identifier, name=invalid_name, result=invalid_result)


@pytest.fixture
def valid_tool_call():
    return ToolCall(identifier="123", name="example_tool", arguments={"arg1": "value1"})


@pytest.fixture
def valid_tool_response():
    return ToolResponse(identifier="123", name="example_tool", result="success")


def test_tool_call_fixture(valid_tool_call):
    assert valid_tool_call.identifier == "123"
    assert valid_tool_call.name == "example_tool"
    assert valid_tool_call.arguments == {"arg1": "value1"}


def test_tool_response_fixture(valid_tool_response):
    assert valid_tool_response.identifier == "123"
    assert valid_tool_response.name == "example_tool"
    assert valid_tool_response.result == "success"