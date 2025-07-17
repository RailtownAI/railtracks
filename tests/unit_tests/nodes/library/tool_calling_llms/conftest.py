import pytest
import requestcompletion as rc
from requestcompletion.llm import AssistantMessage, ToolMessage, ToolResponse, ToolCall
from requestcompletion.llm.response import Response
from pydantic import BaseModel, Field
from ....llm.conftest import MockLLM
from typing import Type

# ============ Mock Model and Functions ===========
@pytest.fixture
def mock_llm() -> Type[MockLLM]:
    return MockLLM

@pytest.fixture
def mock_chat_function():
    def _chat(messages):
        return Response(message=AssistantMessage("dummy content"))
    return _chat

@pytest.fixture
def mock_structured_function():
    def _structured(messages, schema):
        return Response(message=AssistantMessage(schema(text="dummy content", number=42)))
    return _structured

@pytest.fixture
def mock_chat_with_tools_function():    # !!! TODO: this goes on forever, modify logic to be a simple mock
    def _chat_with_tools(messages, tools):
        if len(messages) > 0 and isinstance(messages[-1], ToolMessage) and messages[-1].content.name == "last tool call":
            return Response(message=AssistantMessage("Final answer after tool calls exhausted."))  # mock model expects the tool call name
        if isinstance(messages[-1].content, list):
            # if test tool was requested, mock a response
            return Response(message=AssistantMessage([ToolMessage(ToolResponse(result="dummy content", identifier="test", name="test"))]))
        return Response(message=AssistantMessage([ToolCall(identifier="test", name="test", arguments={})]))  # request a test tool
    
    return _chat_with_tools

# ============ Tools ===========
@pytest.fixture
def mock_tool():
    @rc.to_node
    def magic_number() -> int:
        return 42
    
    return magic_number

# ============ Output Models ===========
@pytest.fixture
def schema():
    class OutputModel(BaseModel):
        value: int = Field(description="A value to extract")
    return OutputModel
