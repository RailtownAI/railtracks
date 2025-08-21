"""Test to verify the fix: warning moves from compile-time to runtime."""

import logging
import pytest
import railtracks as rt
from railtracks.nodes.easy_usage_wrappers.helpers import tool_call_llm
from railtracks.llm import SystemMessage


@rt.function_node
def simple_tool() -> str:
    """A simple test tool."""
    return "Tool executed"


def test_warning_moved_from_creation_to_instantiation(mock_llm, caplog):
    """Test that warning is moved from class creation to instance creation."""
    
    # Clear any existing logs
    caplog.clear()
    
    # Step 1: Create the class - should NOT trigger warning
    with caplog.at_level(logging.WARNING):
        llm_node_class = tool_call_llm(
            tool_nodes={simple_tool.node_type},
            name="Test ToolCallLLM",
            llm_model=mock_llm(),
            max_tool_calls=None,  # This should NOT trigger warning at class creation
            system_message=SystemMessage("Test system message")
        )
    
    # Should have NO warnings at this point
    warning_messages = [record.message for record in caplog.records if record.levelname == "WARNING"]
    unlimited_warnings = [msg for msg in warning_messages if "unlimited tool calls" in msg.lower()]
    assert len(unlimited_warnings) == 0, f"Expected no warnings during class creation but got: {unlimited_warnings}"
    
    # Clear logs before step 2
    caplog.clear()
    
    # Step 2: Instantiate the class - should trigger the runtime warning
    with caplog.at_level(logging.WARNING):
        llm_instance = llm_node_class([rt.llm.UserMessage("Test message")])
    
    # Should have exactly one warning at this point
    warning_messages = [record.message for record in caplog.records if record.levelname == "WARNING"]
    unlimited_warnings = [msg for msg in warning_messages if "unlimited tool calls" in msg.lower()]
    assert len(unlimited_warnings) == 1, f"Expected exactly 1 warning during instantiation but got {len(unlimited_warnings)}: {unlimited_warnings}"
    assert "unlimited tool calls" in unlimited_warnings[0].lower()


def test_no_warning_when_max_tool_calls_is_set(mock_llm, caplog):
    """Test that NO warning appears when max_tool_calls is explicitly set."""
    
    caplog.clear()
    
    with caplog.at_level(logging.WARNING):
        # Create class with explicit max_tool_calls
        llm_node_class = tool_call_llm(
            tool_nodes={simple_tool.node_type},
            name="Test ToolCallLLM Limited",
            llm_model=mock_llm(),
            max_tool_calls=5,  # Explicit limit - should NOT trigger warning
            system_message=SystemMessage("Test system message")
        )
        
        # Instantiate the class
        llm_instance = llm_node_class([rt.llm.UserMessage("Test message")])
    
    # Should have NO warnings throughout the entire process
    warning_messages = [record.message for record in caplog.records if record.levelname == "WARNING"]
    unlimited_warnings = [msg for msg in warning_messages if "unlimited tool calls" in msg.lower()]
    assert len(unlimited_warnings) == 0, f"Expected no warnings when max_tool_calls is set but got: {unlimited_warnings}"