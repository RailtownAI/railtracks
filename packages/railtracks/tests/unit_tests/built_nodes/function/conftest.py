import pytest
from railtracks import ToolManifest
from railtracks.llm import Parameter


@pytest.fixture
def mock_function():
    def f(x : int) -> int:
        return x
    return f

@pytest.fixture
def mock_manifest():
    tool_manifest = ToolManifest(
            description="A tool to be called",
            parameters=[Parameter(
                name="x",
                description="Input to the tool",
                param_type="integer",
            )]
            )
    return tool_manifest
