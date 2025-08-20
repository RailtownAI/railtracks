from typing import Type, Literal

import pytest
import railtracks as rt
from railtracks.llm.response import Response, MessageInfo
from pydantic import BaseModel
from railtracks.llm.message import AssistantMessage, Message


class MockLLM(rt.llm.ModelBase):
    def __init__(self, custom_response_message: str | BaseModel | None = None, requested_tool_calls: list[rt.llm.ToolCall] | None = None):
        """
        Creates a new instance of the MockLLM class.
        Args:
            custom_response_message (Message | None, optional): The custom response message to use for the LLM. Defaults to None.
        """
        super().__init__()
        self.custom_response_message = custom_response_message
        self.requested_tool_calls = requested_tool_calls
        self.mocked_message_info = MessageInfo(
            input_tokens=42,
            output_tokens=42,
            latency=1.42,
            model_name="MockLLM",
            total_cost=0.00042,
            system_fingerprint="fp_4242424242",
        )

    # ================================ HELPERS =================================================
    def _extract_pending_tool_results(self, messages):
        """
        Extract tool results from the end of the message history that need processing.
        """
        tool_results = []
        
        # Look backwards from the end for consecutive tool messages
        for message in reversed(messages):
            if message.role == "tool":
                tool_results.insert(0, message)  # Insert at beginning to maintain order
            else:
                break  # Stop at first non-tool message
        return tool_results
    
    def _make_custom_assistant_message( 
        self,
        default_content: str | BaseModel,
        requested_tool_calls: list[rt.llm.ToolCall] | None = None,
    ) -> AssistantMessage:
        if requested_tool_calls:
            return AssistantMessage(content=requested_tool_calls)
        if self.custom_response_message:
            return AssistantMessage(self.custom_response_message)
        else:
            return AssistantMessage(content=default_content)
    # =======================================================================================
    
    # ================ Base responses (common for sync and async versions) ==================
    def _base_chat(self):
        return Response(
            message=self._make_custom_assistant_message("mocked Message"),
            streamer=None,
            message_info=self.mocked_message_info,
        )
    
    def _base_structured(self):
        class DummyStructured(BaseModel):
            dummy_attr: str = "mocked"

        return Response(
            message=self._make_custom_assistant_message(DummyStructured()),
            streamer=None,
            message_info=self.mocked_message_info,
        )
    
    def _base_chat_with_tools(self, messages):
        tool_results = self._extract_pending_tool_results(messages)
        if tool_results:
            final_message = ""
            for tool_message in tool_results:
               tool_response = tool_message.content
               final_message += f"Tool {tool_response.name} returned: '{tool_response.result}'" + "\n"
            return Response(
                message=rt.llm.Message(content=final_message, role="assistant"),
                streamer=None,
                message_info=self.mocked_message_info,
            )
        else:
            return Response(
                message=self._make_custom_assistant_message("mocked tool message", self.requested_tool_calls),
                streamer=None,
                message_info=self.mocked_message_info,
            )            

    # ==========================================================
    # Override all methods that make network calls with mocks
    async def _achat(self, messages, **kwargs):
        return self._base_chat()

    async def _astructured(self, messages, schema, **kwargs):
        return self._base_structured()

    
    async def _achat_with_tools(self, messages, tools, **kwargs):
        return self._base_chat_with_tools(messages, **kwargs)
    
    async def _astream_chat(self, messages, **kwargs):
        return self._base_chat()

    def _chat(self, messages, **kwargs):
        return self._base_chat()

    def _structured(self, messages, schema, **kwargs):
        return self._base_structured()

    def _chat_with_tools(self, messages, tools, **kwargs):
        return self._base_chat_with_tools(messages, **kwargs)

    def _stream_chat(self, messages, **kwargs):
        return self._base_chat()
    # ==========================================================

    # =====================================
    def model_name(self) -> str | None:
        return "MockLLM"

    @classmethod
    def model_type(cls) -> str | None:
        return "mock"

    # =====================================


@pytest.fixture
def mock_llm() -> Type[MockLLM]:
    """
    Fixture to mock LLM methods with configurable responses.
    Pass a custom_response_message to override the message in all default responses.
    Usage:
        model = mock_model(custom_response_message=rt.llm.Message(content="custom", role="assistant"))
    """
    return MockLLM
