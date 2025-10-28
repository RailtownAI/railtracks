import pytest
from pydantic import BaseModel, Field
from railtracks.llm.message import UserMessage, AssistantMessage, ToolMessage
from railtracks.llm.history import MessageHistory
from railtracks.llm.content import ToolCall, ToolResponse
from railtracks.llm.providers import ModelProvider
from railtracks.llm.tools import Tool, Parameter
from railtracks.llm.models._litellm_wrapper import LiteLLMWrapper

from typing import Any, Optional, Tuple, Union
from litellm.utils import CustomStreamWrapper, ModelResponse  # type: ignore
import logging


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


class MockLogger(logging.Logger):
    def __init__(self):
        super().__init__("mock_logger")

    @property
    def model_call_details(self):
        return {}

    def log(self, level, msg, *args, **kwargs):
        print(msg)

    @property
    def completion_start_time(self):
        return None
    
    def _update_completion_start_time(self, completion_start_time):
        pass

    @property
    def _llm_caching_handler(self):
        return None
    
    def success_handler(self, *args, **kwargs):
        pass



class MockDelta(BaseModel):
    content: str | None
    function_call: list | None = None
    tool_calls: list | None


class MockChoice(BaseModel):
    delta: MockDelta
    finish_reason: str


class ChatCompletionChunk(BaseModel):
    id: str
    choices: list[MockChoice]
    system_fingerprint: None = None


class MockLiteLLMWrapper(LiteLLMWrapper):
    """
    Mock implementation of LiteLLMWrapper for testing purposes.
    """

    def __init__(
        self, model_name=None, content=None, tool_calls=None, stream: bool = False
    ):
        self.content = content or "mock response"
        self.tool_calls = tool_calls
        super().__init__(model_name=model_name or "mock-model", stream=stream)

    @classmethod
    def model_gateway(cls):
        return "mock"
    
    def model_provider(self):
        return self.model_gateway()
    


    def _invoke_content(self):
        return (
            ModelResponse(
                choices=[
                    {
                        "message": {
                            "content": self.content,
                            "tool_calls": self.tool_calls,
                        },
                        "finish_reason": "tool_calls" if self.tool_calls else "stop",
                    }
                ]
            ),
            0.0,
        )

    def _invoke(
        self,
        messages: MessageHistory,
        *,
        response_format: Optional[Any] = None,
        tools: Optional[list[Tool]] = None,
    ) -> Tuple[Union[CustomStreamWrapper, ModelResponse], float]:
        if self.stream:

            def _stream_gen():
                for i, char in enumerate(self.content):
                    yield ChatCompletionChunk(
                        id=str(i),
                        choices=[
                            MockChoice(
                                delta=MockDelta(
                                    content=char,
                                    tool_calls=self.tool_calls,
                                ),
                                finish_reason="",
                            )
                        ],
                    )

                yield ChatCompletionChunk(
                    id=str(len(self.content)),
                    choices=[
                        MockChoice(
                            delta=MockDelta(
                                content=None,
                                tool_calls=None,
                            ),
                            finish_reason="stop",
                        )
                    ],
                )

                yield ChatCompletionChunk(
                    id=str(len(self.content) + 1),
                    choices=[],
                )

            return (
                CustomStreamWrapper(
                    completion_stream=_stream_gen(),
                    model=self.model_name(),
                    logging_obj=MockLogger(),
                ),
                0.0,
            )
        else:
            return self._invoke_content()

    async def _ainvoke(
        self,
        messages: MessageHistory,
        *,
        response_format: Optional[Any] = None,
        tools: Optional[list[Tool]] = None,
    ) -> Tuple[Union[CustomStreamWrapper, ModelResponse], float]:
        if self.stream:

            async def _astream_gen():
                for i, char in enumerate(self.content):
                    yield ChatCompletionChunk(
                        id=str(i),
                        choices=[
                            MockChoice(
                                delta=MockDelta(
                                    content=char,
                                    tool_calls=self.tool_calls,
                                ),
                                finish_reason=(
                                    "stop" if i == len(self.content) else ""
                                ),
                            )
                        ],
                    )
                
                yield ChatCompletionChunk(
                    id=str(len(self.content) + 1),
                    choices=[],
                )

            return (
                CustomStreamWrapper(
                    completion_stream=_astream_gen(),
                    model=self.model_name(),
                    logging_obj=MockLogger(),
                ),
                0.0,
            )
        else:
            return self._invoke_content()


@pytest.fixture
def mock_litellm_wrapper():
    """
    Fixture to provide a mock LiteLLMWrapper instance.
    """
    return MockLiteLLMWrapper


# ======================================= END Mock LiteLLMWrapper ======================================
