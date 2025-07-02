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
    """Test that a node works normally when return_into is None."""
    
    with rc.Runner() as runner:
        # Run the node without return_into parameter
        result = await rc.call(CapitalizeText, "hello world", return_into=None)
        
        # The result should be returned normally
        assert result == "Hello world"


@pytest.mark.asyncio
async def test_return_into_backward_compatibility():
    """Test that existing code without return_into parameter still works.""" 
    
    with rc.Runner() as runner:
        # Run the node the old way (without return_into)
        result = await rc.call(CapitalizeText, "hello world")
        
        # The result should be returned normally
        assert result == "Hello world"


@pytest.mark.asyncio
async def test_return_into_with_prepare_tool():
    """Test that return_into works when nodes are created via prepare_tool method."""
    
    with rc.Runner() as runner:
        # Create node using prepare_tool method with return_into
        tool_params = {"string": "hello world", "return_into": "tool_result"}
        node = CapitalizeText.prepare_tool(tool_params)
        
        # Run the node by calling invoke directly
        result = await node.invoke()
        
        # When calling invoke directly, we still get the result
        # (return_into only applies when run through the Task system)
        assert result == "Hello world"
        
        # But we can verify the return_into parameter was set correctly
        assert node.return_into == "tool_result"


class RelevantFileAgent(rc.Node[str]):
    """Simulates finding a relevant file and returning its content."""
    
    def __init__(self, query: str, **kwargs):
        self.query = query
        super().__init__(**kwargs)
    
    async def invoke(self) -> str:
        # Simulate finding and returning file content
        return f"Content of relevant file for query: {self.query}"
    
    @classmethod
    def pretty_name(cls) -> str:
        return "Relevant File Agent"


class AnalyzeFileAgent(rc.Node[str]):
    """Simulates analyzing file content from context."""
    
    def __init__(self, context_key: str, **kwargs):
        self.context_key = context_key
        super().__init__(**kwargs)
    
    async def invoke(self) -> str:
        # Get file content from context
        file_content = get(self.context_key)
        # Simulate analysis
        return f"Analysis: {file_content} - This appears to be well-structured."
    
    @classmethod
    def pretty_name(cls) -> str:
        return "Analyze File Agent"


@pytest.mark.asyncio
async def test_coordinator_workflow_with_return_into():
    """Test the coordinator workflow mentioned in the feature request."""
    
    with rc.Runner() as runner:
        # Step 1: Coordinator asks RelevantFileAgent to find relevant file
        # The file content is stored in context instead of being returned to coordinator
        result1 = await rc.call(RelevantFileAgent, "machine learning algorithms", return_into="relevant_file")
        
        # Result should be None since it was stored in context
        assert result1 is None
        
        # Verify the file content is in context
        file_content = get("relevant_file")
        assert "Content of relevant file for query: machine learning algorithms" == file_content
        
        # Step 2: Coordinator asks AnalyzeFileAgent to analyze the file from context
        # The coordinator doesn't need to see the file content, saving tokens
        analysis_result = await rc.call(AnalyzeFileAgent, "relevant_file")
        
        # The analysis result is returned normally
        assert "Analysis:" in analysis_result
        assert "machine learning algorithms" in analysis_result
        assert "well-structured" in analysis_result


@pytest.mark.asyncio
async def test_return_into_with_safe_copy():
    """Test that return_into parameter is preserved when using safe_copy method."""
    
    # Create a node with return_into parameter
    original_node = CapitalizeText("hello world", return_into="copied_result")
    
    # Use safe_copy to create a copy
    copied_node = original_node.safe_copy()
    
    # Verify the return_into parameter was copied
    assert copied_node.return_into == "copied_result"
    assert copied_node.string == "hello world"
    
    # Verify they are different instances
    assert copied_node is not original_node
    
    # Note: safe_copy uses deepcopy, so UUID is the same (this is expected behavior)
    # But the functionality should work the same
    assert copied_node.uuid == original_node.uuid