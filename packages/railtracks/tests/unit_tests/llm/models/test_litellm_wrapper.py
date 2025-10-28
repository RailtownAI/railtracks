from typing import Generator
import pytest
from railtracks.llm.models._litellm_wrapper import (
    _parameters_to_json_schema,
    _to_litellm_tool,
)
from railtracks.exceptions import NodeInvocationError, LLMError
from railtracks.llm import AssistantMessage, UserMessage
from pydantic import BaseModel
from railtracks.llm.response import Response
from json import JSONDecodeError
import litellm
from railtracks.llm.content import Stream
import json

class TestHelpers:

    # =================================== START _parameters_to_json_schema Tests ==================================
    # parameters_to_json_schema is guaranteed to get only a set of Parameter objects
    def test_parameters_to_json_schema_with_parameters_set(
        self, tool_with_parameters_set
    ):
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
            _parameters_to_json_schema(123)  # type: ignore

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
    def test_to_litellm_message_user_message(self, mock_litellm_wrapper, user_message):
        """
        Test _to_litellm_message with a UserMessage instance.
        """
        wrapper = mock_litellm_wrapper()
        litellm_message = wrapper._to_litellm_message(user_message)
        assert litellm_message["role"] == "user"
        assert litellm_message["content"] == "This is a user message."

    def test_to_litellm_message_assistant_message(self, mock_litellm_wrapper, assistant_message):
        """
        Test _to_litellm_message with an AssistantMessage instance.
        """
        wrapper = mock_litellm_wrapper()
        litellm_message = wrapper._to_litellm_message(assistant_message)
        assert litellm_message["role"] == "assistant"
        assert litellm_message["content"] == "This is an assistant message."

    def test_to_litellm_message_tool_message(self, mock_litellm_wrapper, tool_message):
        """
        Test _to_litellm_message with a ToolMessage instance.
        """
        wrapper = mock_litellm_wrapper()
        litellm_message = wrapper._to_litellm_message(tool_message)
        assert litellm_message["role"] == "tool"
        assert litellm_message["name"] == "example_tool"
        assert litellm_message["tool_call_id"] == "123"
        assert litellm_message["content"] == "success"

    def test_to_litellm_message_tool_call_list(self, mock_litellm_wrapper, tool_call):
        """
        Test _to_litellm_message with a list of ToolCall instances.
        """
        tool_calls = [tool_call]
        message = AssistantMessage(content=tool_calls)
        wrapper = mock_litellm_wrapper()
        litellm_message = wrapper._to_litellm_message(message)
        assert litellm_message["role"] == "assistant"
        assert len(litellm_message["tool_calls"]) == 1
        assert litellm_message["tool_calls"][0].function.name == "example_tool"

    def test_to_litellm_message_user_message_with_attachments(
        self,
        mock_litellm_wrapper,
    ):
        """
        Test _to_litellm_message handles multimodal user messages with attachments.
        """
        wrapper = mock_litellm_wrapper()
        attachment_data_uri = "data:image/png;base64,iVBORw0KGgo="
        message = UserMessage(
            content="View this image.",
            attachment=[attachment_data_uri],
        )

        litellm_message = wrapper._to_litellm_message(message)

        assert litellm_message["role"] == "user"
        assert isinstance(litellm_message["content"], list)
        assert litellm_message["content"][0] == {
            "type": "text",
            "text": "View this image.",
        }
        assert litellm_message["content"][1] == {
            "type": "image_url",
            "image_url": {"url": attachment_data_uri},
        }

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


# ================= START completion methods tests =========================
class TestCompletionMethods:
    @pytest.mark.parametrize("method_name,is_async,stream", [
        ("_chat", False, False),
        ("_achat", True, False),
        ("_chat", False, True),
    ], ids=["sync_chat", "async_chat", "sync_chat_streaming"])
    @pytest.mark.asyncio
    async def test_chat(self, mock_litellm_wrapper, message_history, method_name, is_async, stream):
        content = "Mission: Impossible" if stream else "Mocked response"
        wrapper = mock_litellm_wrapper(content=content, stream=stream)
        method = getattr(wrapper, method_name)
        
        if is_async:
            result = await method(message_history)
        else:
            result = method(message_history)

        assert isinstance(result, (Response, Generator))
        
        
        if stream:
            result: Generator[str | Response, None, Response]
            for chunk in result:
                if isinstance(chunk, Response):
                    assert isinstance(chunk.message, AssistantMessage)
                    assert chunk.message.content == content
                elif not isinstance(chunk, str):
                    pytest.fail("Stream yielded non-string, non-Response chunk")
        else:
            result: Response
            assert isinstance(result.message, AssistantMessage)
            assert result.message.content == content

    @pytest.mark.parametrize("method_name,is_async,stream", [
        ("_structured", False, False),
        ("_astructured", True, False),
        ("_structured", False, True),
    ], ids=["sync_structured", "async_structured", "sync_structured_streaming"])
    @pytest.mark.asyncio
    async def test_structured(self, mock_litellm_wrapper, message_history, method_name, is_async, stream):
        class ExampleSchema(BaseModel):
            field: str

        wrapper = mock_litellm_wrapper(content='{"field": "VAL"}', stream=stream)
        method = getattr(wrapper, method_name)
        
        if is_async:
            result = await method(message_history, schema=ExampleSchema)
        else:
            result = method(message_history, schema=ExampleSchema)

        assert isinstance(result, (Response, Generator))
        
        
        if stream:
            for chunk in result:
                if isinstance(chunk, Response):
                    print(chunk)
                    assert isinstance(chunk.message, AssistantMessage)
                    assert isinstance(chunk.message.content, ExampleSchema)
                    assert chunk.message.content.field == "VAL"
                elif not isinstance(chunk, str):
                    pytest.fail("Stream yielded non-string, non-Response chunk")

            
        else:
            assert isinstance(result.message, AssistantMessage)
            assert isinstance(result.message.content, ExampleSchema)
            assert result.message.content.field == "VAL"

    @pytest.mark.asyncio
    @pytest.mark.parametrize("method_name,is_async", [
        ("_structured", False),
        ("_astructured", True),
    ], ids=["sync_structured", "async_structured"])
    async def test_structured_schema_jsondecode_error(
        self, mock_litellm_wrapper, message_history, method_name, is_async
    ):
        class Schema(BaseModel):
            val: int

        with pytest.raises(JSONDecodeError):
            wrapper = mock_litellm_wrapper(content="Invalid JSON")
            method = getattr(wrapper, method_name)
            if is_async:
                result = await method(message_history, schema=Schema)
            else:
                result = method(message_history, schema=Schema)

    @pytest.mark.asyncio
    @pytest.mark.parametrize("method_name,is_async", [
        ("_structured", False),
        ("_astructured", True),
    ], ids=["sync_structured", "async_structured"])
    async def test_structured_invalid_json_raises_llm_error(
        self, mock_litellm_wrapper, message_history, method_name, is_async
    ):
        class Schema(BaseModel):
            val: int
        with pytest.raises(LLMError, match="Structured LLM call failed"):
            wrapper = mock_litellm_wrapper(content='{"field": "VAL", "invalid": "json"}')
            method = getattr(wrapper, method_name)
            if is_async:
                result = await method(message_history, schema=Schema)
            else:
                result = method(message_history, schema=Schema)

    @pytest.mark.parametrize("method_name,is_async,stream", [
        ("_chat_with_tools", False, False),
        ("_achat_with_tools", True, False),
        ("_chat_with_tools", False, True),
        # ("_achat_with_tools", True, True),
    ], ids=[
        "sync_chat_with_tools",
        "async_chat_with_tools",
        "sync_chat_with_tools_streaming",
        # "async_chat_with_tools_streaming"
        ])
    @pytest.mark.asyncio
    async def test_chat_with_tools(
        self, mock_litellm_wrapper, message_history, tool, method_name, is_async, stream
    ):
        if stream:
            wrapper = mock_litellm_wrapper(
                content='[{"name": "tool_x", "arguments": {"foo": 1}, "identifier": "id123"}]',
                stream=True,
            )
        else:
            wrapper = mock_litellm_wrapper(
                content=None,
                tool_calls=[
                    litellm.ChatCompletionMessageToolCall(
                        function=litellm.Function(arguments='{"foo": 1}', name="tool_x"),
                        id="id123",
                        type="function",
                    )
                ],
            )
        
        method = getattr(wrapper, method_name)
        if is_async:
            result = await method(message_history, [tool])
        else:
            result = method(message_history, [tool])

        assert isinstance(result, (Response, Generator))

        
        if stream:  # no stream in case the llm requests tool
            for chunk in result:
                if isinstance(chunk, Response):
                    try:
                        calls = json.loads(chunk.message.content)
                        assert isinstance(calls, list)
                        assert calls[0]["name"] == "tool_x"
                        assert calls[0]["arguments"] == {"foo": 1}
                        assert calls[0]["identifier"] == "id123"
                    except Exception as e:
                        pytest.fail("Structured response did not match schema")
                elif not isinstance(chunk, str):
                    pytest.fail("Stream yielded non-string, non-Response chunk")

        else:
            assert isinstance(result.message, AssistantMessage)
            calls = result.message.content
            assert isinstance(calls, list)
            assert calls[0].name == "tool_x"
            assert calls[0].arguments == {"foo": 1}
            assert calls[0].identifier == "id123"

# ================= END completion methods tests =========================