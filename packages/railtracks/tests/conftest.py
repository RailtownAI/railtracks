from typing import Type, Literal

import pytest
import railtracks as rt
from railtracks.llm.response import Response, MessageInfo
from pydantic import BaseModel


class MockLLM(rt.llm.ModelBase):
    def __init__(self, custom_response_message: rt.llm.Message | None = None):
        """
        Creates a new instance of the MockLLM class.
        Args:
            custom_response_message (Message | None, optional): The custom response message to use for the LLM. Defaults to None.
        """
        super().__init__()
        self.custom_response_message = custom_response_message
        self.mocked_message_info = MessageInfo(
            input_tokens=42,
            output_tokens=42,
            latency=1.42,
            model_name="MockLLM",
            total_cost=0.00042,
            system_fingerprint="fp_4242424242",
        )

    def get_message(
        self,
        default_content: str | BaseModel,
        role: Literal["assistant", "user", "system", "tool"] = "assistant",
    ) -> rt.llm.Message:
        return self.custom_response_message or rt.llm.Message(
            content=default_content, role=role
        )
    
    # ================ Base responses (common for sync and async versions) ==================
    def _base_chat(self):
        return Response(
            message=self.get_message("mocked Message"),
            streamer=None,
            message_info=self.mocked_message_info,
        )
    
    def _base_structured(self):
        class DummyStructured(BaseModel):
            dummy_attr: str = "mocked"

        return Response(
            message=self.get_message(DummyStructured()),
            streamer=None,
            message_info=self.mocked_message_info,
        )
    
    def _base_chat_with_tools(self):
        return Response(
            message=self.get_message("mocked tool message"),
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
        return self._base_chat_with_tools()
    
    async def _astream_chat(self, messages, **kwargs):
        return self._base_chat()

    def _chat(self, messages, **kwargs):
        return self._base_chat()

    def _structured(self, messages, schema, **kwargs):
        return self._base_structured()

    def _chat_with_tools(self, messages, tools, **kwargs):
        return self._base_chat_with_tools()

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
