import pytest
import requestcompletion as rc
from requestcompletion.context import put, get

class CapitalizeText(rc.Node[str]):
    def __init__(self, string: str, **kwargs):
        self.string = string
        super().__init__(**kwargs)

    async def invoke(self) -> str:
        return self.string.capitalize()

    @classmethod
    def pretty_name(cls) -> str:
        return "Capitalize Text"


@pytest.mark.asyncio
async def test_call_capitalize_text():
    node = CapitalizeText("hello world")
    assert await node.invoke() == "Hello world"
    assert node.pretty_name() == "Capitalize Text"


@pytest.mark.asyncio
async def test_call_capitalize_text_stream():
    node = CapitalizeText("")

    assert await node.invoke() == ""
    assert node.pretty_name() == "Capitalize Text"


@pytest.mark.asyncio
async def test_return_into_context():
    """Test that a node can return its result into context instead of returning it directly."""
    
    with rc.Runner() as runner:
        # Run the node with return_into parameter
        result = await rc.call(CapitalizeText, "hello world", return_into="text_result")
        
        # The result should be None since it was stored in context
        assert result is None
        
        # The actual result should be in context
        stored_value = get("text_result")
        assert stored_value == "Hello world"


@pytest.mark.asyncio  
async def test_return_into_none():
    """Test that a node works normally when return_into is not set."""
    
    with rc.Runner() as runner:
        # Run the node without return_into parameter
        result = await rc.call(CapitalizeText, "hello world")
        
        # The result should be returned normally
        assert result == "Hello world"
