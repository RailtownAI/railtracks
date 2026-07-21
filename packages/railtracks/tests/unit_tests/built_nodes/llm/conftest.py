from unittest.mock import MagicMock

import pytest
from pydantic import BaseModel
from railtracks import ToolManifest, function_node
from railtracks.llm import Parameter


@pytest.fixture
def mock_llm():
    return MagicMock(name="MockLLM")

@pytest.fixture
def mock_schema():
    class MockSchema(BaseModel):
        x: int
    return MockSchema

@pytest.fixture
def mock_function():
    def f(x : int, y : int) -> int:
        return x + y
    return f

@pytest.fixture
def mock_sys_mes():
    return "This is a system message"

@pytest.fixture
def mock_tool_node():

    tool_manifest = ToolManifest(
        description="A tool to be called",
        parameters=[Parameter(
            name="x",
            description="Input to the tool",
            param_type="integer",
        )]
        )
    def mock_func():
        def f(x : int) -> int:
            return x
        return f

    DummyTool = function_node(mock_func(), name="DummyTool", manifest=tool_manifest)
    return DummyTool

@pytest.fixture
def mock_manifest():
    tool_manifest = ToolManifest(
            description="A tool to be called",
            parameters=[Parameter(
                name="x",
                description="Input to the tool",
                param_type="integer",
            ), Parameter(
                name="y",
                description="Another input to the tool",
                param_type="integer",)]
            )
    return tool_manifest
