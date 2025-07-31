import pytest
from railtracks.llm.models._litellm_wrapper import (
    _parameters_to_json_schema,
    _to_litellm_tool,
    _to_litellm_message,
)
from railtracks.exceptions import NodeInvocationError, LLMError
from railtracks.llm.message import AssistantMessage
from railtracks.llm.history import MessageHistory
from pydantic import BaseModel
import litellm
from typing import Generator


# =================================== START _parameters_to_json_schema Tests ==================================
# parameters_to_json_schema is guaranteed to get only a set of Parameter objects

def test_parameters_to_json_schema_with_parameters_set(tool_with_parameters_set):
    """
    Test _parameters_to_json_schema with a set of Parameter objects.
    """
    schema = _parameters_to_json_schema(tool_with_parameters_set.parameters)
    assert schema["type"] == "object"
    assert "properties" in schema
    assert "param1" in schema["properties"]
    assert schema["properties"]["param1"]["type"] == "string"
    assert schema["properties"]["param1"]["description"] == "A string parameter."
    assert "required" in schema
    assert "param1" in schema["required"]


def test_parameters_to_json_schema_with_empty_set():
    schema = _parameters_to_json_schema(set())
    assert schema == {"type": "object", "properties": {}}


def test_parameters_to_json_schema_invalid_input():
    """
    Test _parameters_to_json_schema with invalid input.
    """
    with pytest.raises(NodeInvocationError):
        _parameters_to_json_schema(123)


# =================================== END _parameters_to_json_schema Tests ====================================


# =================================== START _to_litellm_tool Tests ==================================
def test_to_litellm_tool(tool):
    """
    Test _to_litellm_tool with a valid Tool instance.
    """
    litellm_tool = _to_litellm_tool(tool)
    assert litellm_tool["type"] == "function"
    assert "function" in litellm_tool
    assert litellm_tool["function"]["name"] == "example_tool"
    assert litellm_tool["function"]["description"] == "This is an example tool."
    assert "parameters" in litellm_tool["function"]


# =================================== END _to_litellm_tool Tests ====================================


# =================================== START _to_litellm_message Tests ==================================
def test_to_litellm_message_user_message(user_message):
    """
    Test _to_litellm_message with a UserMessage instance.
    """
    litellm_message = _to_litellm_message(user_message)
    assert litellm_message["role"] == "user"
    assert litellm_message["content"] == "This is a user message."


def test_to_litellm_message_assistant_message(assistant_message):
    """
    Test _to_litellm_message with an AssistantMessage instance.
    """
    litellm_message = _to_litellm_message(assistant_message)
    assert litellm_message["role"] == "assistant"
    assert litellm_message["content"] == "This is an assistant message."


def test_to_litellm_message_tool_message(tool_message):
    """
    Test _to_litellm_message with a ToolMessage instance.
    """
    litellm_message = _to_litellm_message(tool_message)
    assert litellm_message["role"] == "tool"
    assert litellm_message["name"] == "example_tool"
    assert litellm_message["tool_call_id"] == "123"
    assert litellm_message["content"] == "success"


def test_to_litellm_message_tool_call_list(tool_call):
    """
    Test _to_litellm_message with a list of ToolCall instances.
    """
    tool_calls = [tool_call]
    message = AssistantMessage(content=tool_calls)
    litellm_message = _to_litellm_message(message)
    assert litellm_message["role"] == "assistant"
    assert len(litellm_message["tool_calls"]) == 1
    assert litellm_message["tool_calls"][0].function.name == "example_tool"


# =================================== END _to_litellm_message Tests ====================================


# =================================== START LiteLLMWrapper Tests ==================================
@pytest.mark.parametrize(
    "model_name, expected_str",
    [
        ("openai/gpt-3.5-turbo", "LiteLLMWrapper(provider=openai, name=gpt-3.5-turbo)"),
        ("mock-model", "LiteLLMWrapper(name=mock-model)"),
    ],
)
def test_litellm_wrapper_str(model_name, expected_str, mock_litellm_wrapper):
    wrapper = mock_litellm_wrapper(model_name=model_name)
    assert str(wrapper) == expected_str


def test_litellm_wrapper_invoke_with_empty_messages(mock_litellm_wrapper):
    empty_history = MessageHistory([])
    litellm_model = mock_litellm_wrapper(model_name="mock-model")
    result = litellm_model._invoke(empty_history)
    # Validate that the structure of the returned result is correct
    assert "choices" in result
    assert len(result["choices"]) == 1
    assert "message" in result["choices"][0]


def test_litellm_wrapper_structured_schema_mismatch(mock_litellm_wrapper, message_history):
    class ExampleSchema(BaseModel):
        required_value: int

    # Force a response that won't match the output_schema (string instead of int)
    def _invoke_override(*args, **kwargs):
        return ({
            "choices": [
                {
                    "message": {"content": '{"required_value": "not_an_int"}'},
                }
            ]
        }, None)

    litellm_model = mock_litellm_wrapper(model_name="mock-model")
    litellm_model._invoke = _invoke_override

    with pytest.raises(ValueError) as exc_info:
        litellm_model.structured(message_history, ExampleSchema)


def test_litellm_wrapper_structured_invalid_json(mock_litellm_wrapper, message_history):
    class ExampleSchema(BaseModel):
        required_value: int

    # Force a response that's not valid JSON
    def _invoke_override(*args, **kwargs):
        return {
            "choices": [
                {
                    "message": {"content": "Not valid JSON at all"},
                }
            ]
        }

    litellm_model = mock_litellm_wrapper(model_name="mock-model")
    litellm_model._invoke = _invoke_override

    with pytest.raises(LLMError) as exc_info:
        litellm_model.structured(message_history, ExampleSchema)
    assert "Structured LLM call failed" in str(exc_info.value)


def test_litellm_wrapper_stream_chat(mock_litellm_wrapper, message_history):
    # Make a mock streaming response
    def _invoke_override(*args, **kwargs):
        def gen():
            # Simulate streaming parts
            yield litellm.utils.ModelResponse(
                choices=[
                    {"delta": litellm.utils.StreamingChoices(content="Hello")},
                ]
            )
            yield litellm.utils.ModelResponse(
                choices=[
                    {"delta": litellm.utils.StreamingChoices(content=" World")},
                ]
            )

        return gen(), None

    litellm_model = mock_litellm_wrapper(model_name="mock-model")
    litellm_model._invoke = _invoke_override

    response = litellm_model.stream_chat(message_history)
    assert response.message is None
    assert isinstance(response.streamer, Generator)
    chunks = [chunk for chunk in response.streamer]
    assert "".join(chunks) == "Hello World"


def test_litellm_wrapper_chat_with_tools_no_tool_call(mock_litellm_wrapper, message_history, tool):
    def _invoke_override(*args, **kwargs):
        return (litellm.utils.ModelResponse(
            choices=[
                {
                    "message": {"content": "No tool call here"},
                    "finish_reason": "stop",
                }
            ]
        ), None)

    litellm_model = mock_litellm_wrapper(model_name="mock-model")
    litellm_model._invoke = _invoke_override

    response = litellm_model.chat_with_tools(message_history, [tool])
    assert response.message.content == "No tool call here"


def test_litellm_wrapper_chat_with_tools_single_tool_call(mock_litellm_wrapper, message_history, tool):
    def _invoke_override(*args, **kwargs):
        return (litellm.utils.ModelResponse(
            choices=[
                {
                    "message": {
                        "content": "",
                        "tool_calls": [
                            {
                                "function": {"name": "example_tool", "arguments": '{"arg1": "val1"}'},
                                "id": "toolcall-abc",
                            }
                        ],
                    },
                    "finish_reason": "function_call",
                }
            ]
        ), None)

    litellm_model = mock_litellm_wrapper(model_name="mock-model")
    litellm_model._invoke = _invoke_override

    response = litellm_model.chat_with_tools(message_history, [tool])
    calls = response.message.content
    assert len(calls) == 1
    assert calls[0].name == "example_tool"
    assert calls[0].arguments == {"arg1": "val1"}
    assert calls[0].identifier == "toolcall-abc"


# =================================== END LiteLLMWrapper Tests ==================================
