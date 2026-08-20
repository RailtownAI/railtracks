import json
from json import JSONDecodeError
from typing import Generator, Literal
from json import JSONDecodeError
from unittest.mock import patch

import litellm
import pytest
from pydantic import BaseModel
from railtracks.exceptions import LLMError, NodeInvocationError
from railtracks.llm import AssistantMessage, ToolCalls, UserMessage
from railtracks.llm.history import MessageHistory
from railtracks.llm.models._litellm_wrapper import (
    LiteLLMWrapper,
    _parameters_to_json_schema,
    _to_litellm_tool,
)
from railtracks.llm.providers import ModelProvider
from railtracks.llm.response import MessageInfo, Response


class _ConcreteLiteLLMWrapperForTest(LiteLLMWrapper):
    """Minimal concrete LiteLLMWrapper used to test that temperature is passed to litellm.completion."""

    @classmethod
    def model_gateway(cls):
        return ModelProvider.UNKNOWN

    def model_provider(self):
        return ModelProvider.UNKNOWN


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

    def test_to_litellm_message_assistant_message(
        self, mock_litellm_wrapper, assistant_message
    ):
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

    def test_to_litellm_message_tool_call_list_with_text(
        self, mock_litellm_wrapper, tool_call
    ):
        """
        Test _to_litellm_message sends back the text that came with the tool calls.
        """
        message = AssistantMessage(
            content=ToolCalls([tool_call], text="I will call example_tool for you.")
        )
        wrapper = mock_litellm_wrapper()
        litellm_message = wrapper._to_litellm_message(message)
        assert litellm_message["content"] == "I will call example_tool for you."
        assert len(litellm_message["tool_calls"]) == 1

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

    def test_to_litellm_message_user_message_with_pdf_attachment(
        self,
        mock_litellm_wrapper,
    ):
        """
        PDF attachments must be serialized as a "file" content block, not "image_url".
        Data-URI PDFs have no source filename, so the block falls back to "attachment.pdf".
        """
        import base64 as _b64

        wrapper = mock_litellm_wrapper(model_name="gpt-4o")
        pdf_bytes = b"%PDF-1.4\n%fake pdf\n%%EOF"
        b64 = _b64.b64encode(pdf_bytes).decode("utf-8")
        data_uri = f"data:application/pdf;base64,{b64}"
        message = UserMessage(content="Summarize this.", attachment=[data_uri])

        litellm_message = wrapper._to_litellm_message(message)

        assert litellm_message["role"] == "user"
        assert isinstance(litellm_message["content"], list)
        assert litellm_message["content"][0] == {
            "type": "text",
            "text": "Summarize this.",
        }
        file_block = litellm_message["content"][1]
        assert file_block["type"] == "file"
        assert file_block["file"]["file_data"] == data_uri
        assert file_block["file"]["filename"] == "attachment.pdf"

    def test_to_litellm_message_local_pdf_uses_source_filename(
        self,
        mock_litellm_wrapper,
        tmp_path,
    ):
        """
        Local PDF attachments should carry their on-disk filename through to the
        file block, not the data-URI fallback.
        """
        pdf_file = tmp_path / "report.pdf"
        pdf_file.write_bytes(b"%PDF-1.4\n%fake pdf\n%%EOF")

        wrapper = mock_litellm_wrapper(model_name="gpt-4o")
        message = UserMessage(content="Summarize this.", attachment=[str(pdf_file)])

        litellm_message = wrapper._to_litellm_message(message)

        file_block = litellm_message["content"][1]
        assert file_block["type"] == "file"
        assert file_block["file"]["filename"] == "report.pdf"
        assert file_block["file"]["file_data"].startswith(
            "data:application/pdf;base64,"
        )

    def test_to_litellm_message_pdf_attachment_rejected_for_unsupported_model(
        self,
        mock_litellm_wrapper,
    ):
        """
        Serializing a PDF attachment for a model that does not support PDF input
        must raise a clear ValueError naming the model, instead of letting the
        provider 400 later.
        """
        import base64 as _b64

        wrapper = mock_litellm_wrapper(model_name="gpt-3.5-turbo")
        pdf_bytes = b"%PDF-1.4\n%fake pdf\n%%EOF"
        b64 = _b64.b64encode(pdf_bytes).decode("utf-8")
        data_uri = f"data:application/pdf;base64,{b64}"
        message = UserMessage(content="Summarize this.", attachment=[data_uri])

        with pytest.raises(ValueError, match="does not support PDF attachments"):
            wrapper._to_litellm_message(message)

    def test_to_litellm_message_pdf_attachment_allowed_for_unroutable_model(
        self,
        mock_litellm_wrapper,
    ):
        """
        A custom deployment name (Azure Foundry etc.) that litellm can't identify
        must NOT be pre-rejected — the API is the source of truth for capability
        in that case. Regression for the AzureAILLM custom-deployment path.
        """
        import base64 as _b64

        wrapper = mock_litellm_wrapper(model_name="azure/my-custom-deployment")
        pdf_bytes = b"%PDF-1.4\n%fake pdf\n%%EOF"
        b64 = _b64.b64encode(pdf_bytes).decode("utf-8")
        data_uri = f"data:application/pdf;base64,{b64}"
        message = UserMessage(content="Summarize this.", attachment=[data_uri])

        litellm_message = wrapper._to_litellm_message(message)

        file_block = litellm_message["content"][1]
        assert file_block["type"] == "file"

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
    @pytest.mark.parametrize("method_name,is_async", [
        ("_chat", False),
        ("_achat", True),
    ], ids=["sync_chat", "async_chat"])
    @pytest.mark.asyncio
    async def test_chat(self, mock_litellm_wrapper, message_history, method_name, is_async):
        content = "Mocked response"
        wrapper = mock_litellm_wrapper(content=content)
        method = getattr(wrapper, method_name)

        if is_async:
            result = await method(message_history)
        else:
            result = method(message_history)

        assert isinstance(result, Response)
        assert isinstance(result.message, AssistantMessage)
        assert result.message.content == content

    @pytest.mark.parametrize("method_name,is_async", [
        ("_structured", False),
        ("_astructured", True),
    ], ids=["sync_structured", "async_structured"])
    @pytest.mark.asyncio
    async def test_structured(self, mock_litellm_wrapper, message_history, method_name, is_async):
        class ExampleSchema(BaseModel):
            field: str

        wrapper = mock_litellm_wrapper(content='{"field": "VAL"}')
        method = getattr(wrapper, method_name)

        if is_async:
            result = await method(message_history, schema=ExampleSchema)
        else:
            result = method(message_history, schema=ExampleSchema)

        assert isinstance(result, Response)
        assert isinstance(result.message, AssistantMessage)
        assert isinstance(result.message.content, ExampleSchema)
        assert result.message.content.field == "VAL"

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "method_name,is_async",
        [
            ("_structured", False),
            ("_astructured", True),
        ],
        ids=["sync_structured", "async_structured"],
    )
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
    @pytest.mark.parametrize(
        "method_name,is_async",
        [
            ("_structured", False),
            ("_astructured", True),
        ],
        ids=["sync_structured", "async_structured"],
    )
    async def test_structured_invalid_json_raises_llm_error(
        self, mock_litellm_wrapper, message_history, method_name, is_async
    ):
        class Schema(BaseModel):
            val: int

        with pytest.raises(LLMError, match="Structured LLM call failed"):
            wrapper = mock_litellm_wrapper(
                content='{"field": "VAL", "invalid": "json"}'
            )
            method = getattr(wrapper, method_name)
            if is_async:
                result = await method(message_history, schema=Schema)
            else:
                result = method(message_history, schema=Schema)

    @pytest.mark.parametrize("method_name,is_async", [
        ("_chat_with_tools", False),
        ("_achat_with_tools", True),
    ], ids=[
        "sync_chat_with_tools",
        "async_chat_with_tools",
        ])
    @pytest.mark.asyncio
    async def test_chat_with_tools(
        self, mock_litellm_wrapper, message_history, tool, method_name, is_async
    ):
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

        assert isinstance(result, Response)
        assert isinstance(result.message, AssistantMessage)
        calls = result.message.content
        assert isinstance(calls, list)
        assert calls[0].name == "tool_x"
        assert calls[0].arguments == {"foo": 1}
        assert calls[0].identifier == "id123"


# ================= START async streaming (sync bridge) tests =========================
class TestAsyncStreaming:
    """Exercise the per-call `astream_*` surface, which rides the synchronous
    `litellm.completion(stream=True)` bridged onto the event loop by `_bridge_sync_stream`.

    Streaming is requested per call via `astream_*`; there is no constructor-level stream
    flag."""

    @pytest.mark.asyncio
    async def test_astream_chat_yields_chunks_then_response(self, mock_litellm_wrapper):
        wrapper = mock_litellm_wrapper(content="Hello")

        chunks: list[str] = []
        final: Response | None = None
        async for item in wrapper.astream_chat(MessageHistory([UserMessage("hi")])):
            if isinstance(item, Response):
                final = item
            else:
                chunks.append(item)

        assert "".join(chunks) == "Hello"
        assert final is not None
        assert isinstance(final.message, AssistantMessage)
        assert final.message.content == "Hello"

    @pytest.mark.asyncio
    async def test_astream_structured_final_is_parsed(self, mock_litellm_wrapper):
        class ExampleSchema(BaseModel):
            field: str

        wrapper = mock_litellm_wrapper(content='{"field": "VAL"}')

        final: Response | None = None
        async for item in wrapper.astream_structured(
            MessageHistory([UserMessage("hi")]), schema=ExampleSchema
        ):
            if isinstance(item, Response):
                final = item

        assert final is not None
        assert isinstance(final.message.content, ExampleSchema)
        assert final.message.content.field == "VAL"

    @pytest.mark.asyncio
    async def test_astream_chat_early_break_is_clean(self, mock_litellm_wrapper):
        """Breaking out early must not raise or hang (the worker is signalled to stop and the
        underlying stream is closed on its own thread)."""
        wrapper = mock_litellm_wrapper(content="abcdef")

        got = None
        async for item in wrapper.astream_chat(MessageHistory([UserMessage("hi")])):
            if isinstance(item, str):
                got = item
                break

        assert got is not None

    @pytest.mark.asyncio
    async def test_astream_chat_with_tools_yields_final_tool_call_response(
        self, mock_litellm_wrapper
    ):
        """astream_chat_with_tools was previously untested -- the fixture already
        threads `tool_calls` into every streamed delta (mirroring the non-streamed
        `test_chat_with_tools` above), it just had no direct astream test."""
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

        chunks: list[str] = []
        final: Response | None = None
        async for item in wrapper.astream_chat_with_tools(
            MessageHistory([UserMessage("hi")]), tools=[]
        ):
            if isinstance(item, Response):
                final = item
            else:
                chunks.append(item)

        assert final is not None
        assert isinstance(final.message, AssistantMessage)
        calls = final.message.content
        assert isinstance(calls, list)
        assert calls[0].name == "tool_x"
        assert calls[0].identifier == "id123"

    @pytest.mark.asyncio
    async def test_astream_chat_propagates_errors(self, mock_litellm_wrapper):
        wrapper = mock_litellm_wrapper(content="Hello")

        def _boom(*args, **kwargs):
            raise RuntimeError("stream open failed")

        with patch.object(wrapper, "_invoke", side_effect=_boom):
            with pytest.raises(RuntimeError, match="stream open failed"):
                async for _ in wrapper.astream_chat(MessageHistory([UserMessage("hi")])):
                    pass


# ================= END async streaming (sync bridge) tests =========================

    @pytest.mark.parametrize(
        "method_name,is_async",
        [
            ("_chat_with_tools", False),
            ("_achat_with_tools", True),
        ],
        ids=["sync_chat_with_tools", "async_chat_with_tools"],
    )
    @pytest.mark.asyncio
    async def test_chat_with_tools_keeps_text_returned_with_tool_calls(
        self, mock_litellm_wrapper, message_history, tool, method_name, is_async
    ):
        """
        Models often answer with prose and a tool call in the same message. The prose
        must survive alongside the tool calls instead of being dropped.
        """
        wrapper = mock_litellm_wrapper(
            content="I will call tool_x with foo=1.",
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

        assert result.message.content[0].name == "tool_x"
        assert result.message.content.text == "I will call tool_x with foo=1."

    def test_prepare_response_keeps_streamed_text_with_tool_calls(
        self, mock_litellm_wrapper, tool_call
    ):
        """
        The same applies to the streaming path, where the text arrives as content deltas.
        """
        wrapper = mock_litellm_wrapper()
        response = wrapper._prepare_response(
            accumulated_content="I will call example_tool for you.",
            tools=[tool_call],
            output_schema=None,
            message_info=MessageInfo(),
        )

        assert response.message.content == [tool_call]
        assert response.message.content.text == "I will call example_tool for you."


def test_temperature_passed_to_litellm_completion(message_history):
    """Assert that when a LiteLLMWrapper is created with temperature, it is passed to litellm.completion."""
    with patch.object(litellm, "completion") as mock_completion:
        mock_completion.return_value = litellm.utils.ModelResponse(
            choices=[{"message": {"content": "ok"}}]
        )
        wrapper = _ConcreteLiteLLMWrapperForTest(
            model_name="test-model", temperature=0.5
        )
        wrapper.chat(message_history)
        mock_completion.assert_called_once()
        assert mock_completion.call_args.kwargs.get("temperature") == 0.5


@pytest.mark.asyncio
async def test_temperature_passed_through_async_chat(message_history):
    """The async surface (`achat`) runs the sync `litellm.completion` on a worker thread, so
    temperature must still reach litellm."""
    with patch.object(litellm, "completion") as mock_completion:
        mock_completion.return_value = litellm.utils.ModelResponse(
            choices=[{"message": {"content": "ok"}}]
        )
        wrapper = _ConcreteLiteLLMWrapperForTest(
            model_name="test-model", temperature=0.7
        )
        await wrapper.achat(message_history)
        mock_completion.assert_called_once()
        assert mock_completion.call_args.kwargs.get("temperature") == 0.7


# ================= END completion methods tests =========================

# ================= START common hyperparameter support tests =========================


@pytest.mark.parametrize(
    "kwarg_name,kwarg_value",
    [
        ("top_p", 0.9),
        ("max_tokens", 256),
        ("frequency_penalty", 0.3),
        ("presence_penalty", 0.2),
        ("reasoning_effort", "high"),
        ("service_tier", "FAST"),
        ("verbosity", "low"),
    ],
)
def test_common_hyperparameter_passed_to_litellm_completion(
    kwarg_name, kwarg_value, message_history
):
    """Assert that new common hyperparameters are threaded through to litellm.completion when set."""
    with patch.object(litellm, "completion") as mock_completion:
        mock_completion.return_value = litellm.utils.ModelResponse(
            choices=[{"message": {"content": "ok"}}]
        )
        wrapper = _ConcreteLiteLLMWrapperForTest(
            model_name="test-model", **{kwarg_name: kwarg_value}
        )
        wrapper.chat(message_history)
        mock_completion.assert_called_once()
        assert mock_completion.call_args.kwargs.get(kwarg_name) == kwarg_value


# ================= END common hyperparameter support tests =========================

# ================= START #1394 reasoning_effort-default-for-tools tests =============


class TestReasoningEffortDefaultForTools:
    """#1394 regression: reasoning-capable models (gpt-5.4+ family) reject function tools
    on /v1/chat/completions when reasoning_effort is left unset, because OpenAI silently
    substitutes a non-'none' default server-side. The wrapper must default
    reasoning_effort='none' in exactly that situation and leave every other case alone."""

    @staticmethod
    def _patch_model_info(monkeypatch, **info):
        import railtracks.llm.models._hyperparameter_support as hyperparameter_support_module

        monkeypatch.setattr(
            hyperparameter_support_module.litellm,
            "get_model_info",
            lambda model: info,
        )

    def test_reasoning_effort_defaulted_to_none_for_tool_call(
        self, message_history, tool, monkeypatch
    ):
        self._patch_model_info(
            monkeypatch, supports_reasoning=True, supports_none_reasoning_effort=True
        )
        with patch.object(litellm, "completion") as mock_completion:
            mock_completion.return_value = litellm.utils.ModelResponse(
                choices=[
                    {
                        "message": {"content": "ok", "tool_calls": None},
                        "finish_reason": "stop",
                    }
                ]
            )
            wrapper = _ConcreteLiteLLMWrapperForTest(model_name="openai/gpt-5.6-sol")
            wrapper.chat_with_tools(message_history, [tool])
            mock_completion.assert_called_once()
            assert mock_completion.call_args.kwargs.get("reasoning_effort") == "none"

    def test_explicit_reasoning_effort_not_overridden(
        self, message_history, tool, monkeypatch
    ):
        self._patch_model_info(
            monkeypatch, supports_reasoning=True, supports_none_reasoning_effort=True
        )
        with patch.object(litellm, "completion") as mock_completion:
            mock_completion.return_value = litellm.utils.ModelResponse(
                choices=[
                    {
                        "message": {"content": "ok", "tool_calls": None},
                        "finish_reason": "stop",
                    }
                ]
            )
            wrapper = _ConcreteLiteLLMWrapperForTest(
                model_name="openai/gpt-5.6-sol", reasoning_effort="high"
            )
            wrapper.chat_with_tools(message_history, [tool])
            assert mock_completion.call_args.kwargs.get("reasoning_effort") == "high"

    def test_no_default_added_without_tools(self, message_history, monkeypatch):
        self._patch_model_info(
            monkeypatch, supports_reasoning=True, supports_none_reasoning_effort=True
        )
        with patch.object(litellm, "completion") as mock_completion:
            mock_completion.return_value = litellm.utils.ModelResponse(
                choices=[{"message": {"content": "ok"}}]
            )
            wrapper = _ConcreteLiteLLMWrapperForTest(model_name="openai/gpt-5.6-sol")
            wrapper.chat(message_history)
            assert "reasoning_effort" not in mock_completion.call_args.kwargs

    def test_no_default_for_non_reasoning_model(self, message_history, tool, monkeypatch):
        self._patch_model_info(
            monkeypatch, supports_reasoning=None, supports_none_reasoning_effort=None
        )
        with patch.object(litellm, "completion") as mock_completion:
            mock_completion.return_value = litellm.utils.ModelResponse(
                choices=[
                    {
                        "message": {"content": "ok", "tool_calls": None},
                        "finish_reason": "stop",
                    }
                ]
            )
            wrapper = _ConcreteLiteLLMWrapperForTest(model_name="openai/gpt-4o")
            wrapper.chat_with_tools(message_history, [tool])
            assert "reasoning_effort" not in mock_completion.call_args.kwargs


# ================= END #1394 reasoning_effort-default-for-tools tests ===============
