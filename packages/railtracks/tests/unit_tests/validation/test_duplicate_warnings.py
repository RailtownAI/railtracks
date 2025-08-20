"""Test to verify duplicate warning fix for unlimited tool calls."""

import pytest
import logging
import io
from railtracks.nodes.easy_usage_wrappers.helpers import tool_call_llm
from railtracks.llm import SystemMessage, Tool, MessageHistory, UserMessage
from railtracks.nodes.nodes import Node
from railtracks.nodes.concrete import ToolCallLLM
from railtracks.utils.logging import get_rt_logger


class SimpleToolNode(Node):
    @classmethod
    def name(cls):
        return "SimpleToolNode"
    
    @classmethod 
    def tool_info(cls):
        return Tool(name="simple_tool", detail="A simple test tool", parameters=None)
    
    def execute(self, **kwargs):
        return "Tool executed"


def test_unlimited_tool_calls_single_warning(mock_llm, caplog):
    """Test that unlimited tool calls warning only appears once during the full lifecycle."""
    
    # Clear any existing logs
    caplog.clear()
    
    with caplog.at_level(logging.WARNING):
        # Step 1: Create ToolCallLLM with max_tool_calls=None
        llm_node = tool_call_llm(
            tool_nodes={SimpleToolNode},
            name="Test ToolCallLLM",
            llm_model=mock_llm(),
            max_tool_calls=None,  # This should trigger creation warning
            system_message=SystemMessage("Test system message")
        )
        
        # Step 2: Create a direct ToolCallLLM instance that would trigger runtime warning
        class TestToolCallLLM(ToolCallLLM):
            max_tool_calls = None  # Set to None to potentially trigger warning
            
            @classmethod
            def name(cls):
                return "TestDirectLLM"
            
            def tool_nodes(self):
                return {SimpleToolNode}
        
        # Create message history and instantiate directly
        mh = MessageHistory([SystemMessage("test"), UserMessage("test")])
        direct_node = TestToolCallLLM(user_input=mh, llm_model=mock_llm())
    
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
            tool_nodes={SimpleToolNode},
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


def test_unlimited_tool_calls_no_runtime_warning(mock_llm, caplog):
    """Test that runtime doesn't emit warning for unlimited tool calls."""
    
    class TestToolCallLLM(ToolCallLLM):
        max_tool_calls = None  # Set to None
        
        @classmethod
        def name(cls):
            return "TestDirectLLM"
        
        def tool_nodes(self):
            return {SimpleToolNode}
    
    # Clear any existing logs
    caplog.clear()
    
    with caplog.at_level(logging.WARNING):
        # Create message history and instantiate directly (runtime only)
        mh = MessageHistory([SystemMessage("test"), UserMessage("test")])
        direct_node = TestToolCallLLM(user_input=mh, llm_model=mock_llm())
    
    # Should NOT have any warnings about unlimited tool calls in runtime
    warning_messages = [record.message for record in caplog.records if record.levelname == "WARNING"]
    unlimited_warnings = [msg for msg in warning_messages if "unlimited tool calls" in msg.lower()]
    
    assert len(unlimited_warnings) == 0, f"Expected no runtime warnings but got: {unlimited_warnings}"