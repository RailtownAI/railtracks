from typing import Type, Literal
from urllib import response

import pytest
import railtracks as rt
from railtracks.llm.providers import ModelProvider
from railtracks.llm.response import Response, MessageInfo
from railtracks.llm.content import Stream
from pydantic import BaseModel
from railtracks.llm.message import AssistantMessage, Message
import json


class MockLLM(rt.llm.ModelBase):
    def __init__(
        self,
        custom_response: str | None = None,
        requested_tool_calls: list[rt.llm.ToolCall] | None = None,
        stream: bool = False,
    ):
        """
        Creates a new instance of the MockLLM class.
        Args:
            custom_response_message (Message | None, optional): The custom response message to use for the LLM. Defaults to None.
        """
        super().__init__(stream=stream)
        self.custom_response = custom_response
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

    # =======================================================================================

    # ================ Base responses (common for sync and async versions) ==================
    def _base_chat(self):
        if self.custom_response:
            assert isinstance(self.custom_response, str), "custom_response must be a string for terminal LLMs"
        return_message = self.custom_response or "mocked Message"
        # Streaming case
        if self.stream:
            def make_generator():
                    for char in return_message:
                        yield char

                    r = Response(
                        message=AssistantMessage(content=return_message),
                        message_info=self.mocked_message_info,
                    )
                    yield r 
                    return r
                
            return make_generator()
        
        # general case 
        return Response(
            message=AssistantMessage(return_message),
            message_info=self.mocked_message_info,
        )

    def _base_structured(self, messages, schema):
        class DummyStructured(BaseModel):
            dummy_attr: str = "mocked"

        if self.custom_response:
            response_model = schema(**json.loads(self.custom_response))
        else:
            response_model = DummyStructured()

        # Streaming case
        if self.stream:
            def make_generator():
                    for char in response_model.model_dump_json():
                        yield char

                    r = Response(
                        message=AssistantMessage(content=response_model),
                        message_info=self.mocked_message_info,
                    )
                    yield r 
                    return r
                
            return make_generator()

        return Response(
            message=AssistantMessage(response_model),
            message_info=self.mocked_message_info,
        )

    def _base_chat_with_tools(self, messages):
        tool_results = self._extract_pending_tool_results(messages)
        if tool_results:
            final_message = ""
            for tool_message in tool_results:
                tool_response = tool_message.content
                final_message += (
                    f"Tool {tool_response.name} returned: '{tool_response.result}'"
                    + "\n"
                )
            # Streaming case
            if self.stream:
                def make_generator():
                    for char in final_message:
                        yield char

                    r = Response(
                        message=AssistantMessage(content=final_message),
                        message_info=self.mocked_message_info,
                    )
                    yield r 
                    return r
                
                return make_generator()
            
            return Response(    # no changes in this response in case of streaming
                message=AssistantMessage(content=final_message),
                message_info=self.mocked_message_info,
            )
        else:
            return_message = self.requested_tool_calls or "mocked tool message"
            r = Response(    # no changes in this response in case of streaming
                message=AssistantMessage(return_message),
                message_info=self.mocked_message_info,
            )
            if self.stream:
                def tool_generator():
                    yield r
                    return r
                return tool_generator()
            else:
                return r


    # ==========================================================
    # Override all methods that make network calls with mocks
    async def _achat(self, messages, **kwargs):
        return self._base_chat()

    async def _astructured(self, messages, schema, **kwargs):
        return self._base_structured(messages, schema)

    async def _achat_with_tools(self, messages, tools, **kwargs):
        return self._base_chat_with_tools(messages, **kwargs)

    async def _astream_chat(self, messages, **kwargs):
        return self._base_chat()

    def _chat(self, messages, **kwargs):
        return self._base_chat()

    def _structured(self, messages, schema, **kwargs):
        return self._base_structured(messages, schema)

    def _chat_with_tools(self, messages, tools, **kwargs):
        return self._base_chat_with_tools(messages, **kwargs)

    def _stream_chat(self, messages, **kwargs):
        return self._base_chat()

    # ==========================================================

    # =====================================
    def model_name(self) -> str | None:
        return "MockLLM"

    @classmethod
    def model_gateway(cls) -> str | None:
        return "mock"
    
    def model_provider(self):
        return self.model_gateway()

    # =====================================


@pytest.fixture
def mock_llm() -> Type[MockLLM]:
    """
    Fixture to mock LLM methods with configurable responses.
    Pass a custom_response_message to override the message in all default responses.
    Usage:
        model = mock_model(
                    custom_response_message=r"custom")
                    requested_tool_calls=[ToolCall(name="secret_phrase", identifier="id_42424242", arguments={})]
                )
    """
    return MockLLM
