from pydantic import BaseModel
import pytest
import railtracks as rt



@pytest.fixture
def schema():
    class DummySchema(BaseModel):
        value: int

    return DummySchema

@pytest.fixture
def mock_tool():
    @rt.function_node
    def dummy_tool(param1: int, param2: str) -> str:
        return f"param1: {param1}, param2: {param2}"
    
    return dummy_tool.node_type