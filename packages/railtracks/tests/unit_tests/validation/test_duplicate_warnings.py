"""Test to verify duplicate warning fix for unlimited tool calls."""

import pytest
import logging
import railtracks as rt
from railtracks.nodes.easy_usage_wrappers.helpers import tool_call_llm
from railtracks.llm import SystemMessage


@rt.function_node
def simple_tool() -> str:
    """A simple test tool."""
    return "Tool executed"


def test_unlimited_tool_calls_single_warning(mock_llm, caplog):
    """Test that unlimited tool calls warning only appears once during the full lifecycle."""
    
    # Clear any existing logs
    caplog.clear()
    
    with caplog.at_level(logging.WARNING):
        # Create ToolCallLLM with max_tool_calls=None - should trigger creation warning
        llm_node = tool_call_llm(
            tool_nodes={simple_tool.node_type},
            name="Test ToolCallLLM",
            llm_model=mock_llm(),
            max_tool_calls=None,  # This should trigger creation warning
            system_message=SystemMessage("Test system message")
        )
    
    # Count how many times the warning appears
    warning_messages = [record.message for record in caplog.records if record.levelname == "WARNING"]
    unlimited_warnings = [msg for msg in warning_messages if "unlimited tool calls" in msg.lower()]
    
    # We should only see the warning once (during creation), not twice
    assert len(unlimited_warnings) == 1, f"Expected exactly 1 warning but got {len(unlimited_warnings)}: {unlimited_warnings}"
    assert "unlimited tool calls" in unlimited_warnings[0].lower()


def test_unlimited_tool_calls_creation_warning_only(mock_llm, caplog):
    """Test that creation-time warning still works."""
    
    with caplog.at_level(logging.WARNING):
        _ = tool_call_llm(
            tool_nodes={simple_tool.node_type},
            name="Test ToolCallLLM",
            llm_model=mock_llm(),
            max_tool_calls=None,
            system_message=SystemMessage("Test system message")
        )
    
    # Should have the creation warning
    warning_messages = [record.message for record in caplog.records if record.levelname == "WARNING"]
    unlimited_warnings = [msg for msg in warning_messages if "unlimited tool calls" in msg.lower()]
    
    assert len(unlimited_warnings) == 1
    assert "unlimited tool calls" in unlimited_warnings[0].lower()