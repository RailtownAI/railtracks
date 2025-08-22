import pytest
import railtracks as rt
from railtracks.llm import AssistantMessage, ToolMessage, ToolResponse, ToolCall
from railtracks.llm.response import Response
from pydantic import BaseModel, Field
from typing import Type

# ============ Tools ===========
@pytest.fixture
def mock_tool():
    @rt.function_node
    def magic_number() -> int:
        return 42
    
    return magic_number.node_type

# ============ Output Models ===========
@pytest.fixture
def schema():
    class OutputModel(BaseModel):
        value: int = Field(description="A value to extract")
    return OutputModel
