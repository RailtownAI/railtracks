import pytest
from unittest.mock import MagicMock

@pytest.fixture
def mock_llm():
    return MagicMock(name="MockLLM")

@pytest.fixture
def mock_tool_node():
    class DummyTool:
        pass
    return DummyTool

@pytest.fixture
def mock_function():
    def f(x):
        return x
    return f

@pytest.fixture
def mock_manifest():
    class Manifest:
        description = "desc"
        parameters = {"x": "int"}
    return Manifest()