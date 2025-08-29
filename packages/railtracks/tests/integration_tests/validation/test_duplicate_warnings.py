"""Test to verify duplicate warning fix for unlimited tool calls."""

import logging
import railtracks as rt
from railtracks.built_nodes.easy_usage_wrappers.helpers import tool_call_llm
from railtracks.llm import SystemMessage


@rt.function_node
def simple_tool() -> str:
    """A simple test tool."""
    return "Tool executed"


def test_unlimited_tool_calls_single_warning(mock_llm, caplog):
    """Test that unlimited tool calls warning only appears once during runtime invocation."""
    
    # Clear any existing logs
    caplog.clear()
    # Create ToolCallLLM class - should NOT trigger warning anymore
    llm_node_class = tool_call_llm(
            tool_nodes={simple_tool},
            name="Test ToolCallLLM",
            llm=mock_llm(),
            max_tool_calls=None,  # This should NOT trigger warning at class creation
            system_message=SystemMessage("Test system message")
        )
    
    with caplog.at_level(logging.WARNING):
        
        # Instantiate the node - this should trigger the runtime warning
        llm_instance = llm_node_class([rt.llm.UserMessage("Test message")])
    
    # Count how many times the warning appears
    warning_messages = [record.message for record in caplog.records if record.levelname == "WARNING"]
    unlimited_warnings = [msg for msg in warning_messages if "unlimited tool calls" in msg.lower()]
    
    # We should only see the warning once (during instantiation), not twice
    assert len(unlimited_warnings) == 1, f"Expected exactly 1 warning but got {len(unlimited_warnings)}: {unlimited_warnings}"
    assert "unlimited tool calls" in unlimited_warnings[0].lower()


def test_unlimited_tool_calls_not_creation_warning(mock_llm, caplog):
    """Test that runtime warning appears correctly when node is instantiated."""

    # Create class - should NOT trigger warning
    llm_node_class = tool_call_llm(
            tool_nodes={simple_tool},
            name="Test ToolCallLLM",
            llm=mock_llm(),
            max_tool_calls=10,
            system_message=SystemMessage("Test system message")
        )
    
    with caplog.at_level(logging.WARNING):
        
        
        # Instantiate - should trigger the runtime warning
        _ = llm_node_class([rt.llm.UserMessage("Test message")])
    
    # Should have the runtime warning
    warning_messages = [record.message for record in caplog.records if record.levelname == "WARNING"]
    unlimited_warnings = [msg for msg in warning_messages if "unlimited tool calls" in msg.lower()]
    
    assert len(unlimited_warnings) == 0, "There should be no matching warnings"