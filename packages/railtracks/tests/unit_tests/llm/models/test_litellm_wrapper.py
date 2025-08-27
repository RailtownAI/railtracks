import pytest
import types
from railtracks.llm.models._litellm_wrapper import (
    _parameters_to_json_schema,
    _to_litellm_tool,
    _to_litellm_message,
)
from railtracks.exceptions import NodeInvocationError, LLMError
from railtracks.llm.message import AssistantMessage
from pydantic import BaseModel
from railtracks.llm.response import Response

class TestHelpers:

    # =================================== START _parameters_to_json_schema Tests ==================================
    # parameters_to_json_schema is guaranteed to get only a set of Parameter objects
    def test_parameters_to_json_schema_with_parameters_set(self, tool_with_parameters_set):
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


    def test_parameters_to_json_schema_with_empty_set(self):
        schema = _parameters_to_json_schema(set())
        assert schema == {"type": "object", "properties": {}}


    def test_parameters_to_json_schema_invalid_input(self):
        """
        Test _parameters_to_json_schema with invalid input.
        """
        with pytest.raises(NodeInvocationError):
            _parameters_to_json_schema(123)     # type: ignore


    # =================================== END _parameters_to_json_schema Tests ====================================


    # =================================== START _to_litellm_tool Tests ==================================
    def test_to_litellm_tool(self, tool):
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
    def test_to_litellm_message_user_message(self, user_message):
        """
        Test _to_litellm_message with a UserMessage instance.
        """
        litellm_message = _to_litellm_message(user_message)
        assert litellm_message["role"] == "user"
        assert litellm_message["content"] == "This is a user message."


    def test_to_litellm_message_assistant_message(self, assistant_message):
        """
        Test _to_litellm_message with an AssistantMessage instance.
        """
        litellm_message = _to_litellm_message(assistant_message)
        assert litellm_message["role"] == "assistant"
        assert litellm_message["content"] == "This is an assistant message."


    def test_to_litellm_message_tool_message(self, tool_message):
        """
        Test _to_litellm_message with a ToolMessage instance.
        """
        litellm_message = _to_litellm_message(tool_message)
        assert litellm_message["role"] == "tool"
        assert litellm_message["name"] == "example_tool"
        assert litellm_message["tool_call_id"] == "123"
        assert litellm_message["content"] == "success"


    def test_to_litellm_message_tool_call_list(self, tool_call):
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


# ================= BEGIN str/model_name (smoke) ==================
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

def test_litellm_wrapper_model_name_property(mock_litellm_wrapper):
    wrapper = mock_litellm_wrapper(model_name="mock-model")
    assert wrapper.model_name() == "mock-model"
# ================= END str/model_name (smoke) ==================

# ================= START sync tests =========================
class TestSync:

    def test_chat_returns_response(self, mock_litellm_wrapper, message_history):
        wrapper = mock_litellm_wrapper(response="Mocked response")
        result = wrapper._chat(message_history)
        assert isinstance(result, Response)
        assert isinstance(result.message, AssistantMessage)

    def test_structured_returns_response(self, mock_litellm_wrapper, message_history):
        class ExampleSchema(BaseModel):
            field: str
        wrapper = mock_litellm_wrapper(response=ExampleSchema(field="VAL"))
        result = wrapper._structured(message_history, schema=ExampleSchema)
        assert isinstance(result.message.content, ExampleSchema)
        assert result.message.content.field == "VAL"

    def test_structured_schema_validation_error(self, mock_litellm_wrapper, message_history):
        class Schema(BaseModel):
            val: int 
        result = mock_litellm_wrapper._structured(message_history, Schema)
        assert isinstance(result.message.content, ValidationError)

    def test_structured_invalid_json_raises_llm_error(self,  mock_litellm_wrapper, message_history):
        class Schema(BaseModel):
            val: int 
        result = mock_litellm_wrapper._structured(message_history, Schema)
        assert isinstance(result.message.content, LLMError)
        assert "Structured LLM call failed" in str(result.message.content)

    def test_chat_with_tools_tool_call(self, mock_litellm_wrapper, message_history, tool):
        result = mock_litellm_wrapper._chat_with_tools(message_history, [tool])
        calls = result.message.content
        assert isinstance(calls, list)
        assert calls[0].name == "tool_x"
        assert calls[0].arguments == {"foo": 1}
        assert calls[0].identifier == "id123"
    # ================= END sync tests =========================