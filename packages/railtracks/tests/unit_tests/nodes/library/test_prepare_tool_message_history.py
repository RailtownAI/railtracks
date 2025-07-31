import pytest
from typing import Dict, Any

from railtracks.llm import MessageHistory, Parameter, UserMessage
from railtracks.nodes.concrete import LLMBase


class TestPrepareToolMessageHistory:
    """Test the prepare_tool_message_history method in LLMBase."""

    def test_empty_parameters(self):
        """Test that empty parameters return an empty message history."""
        message_history = LLMBase.prepare_tool_message_history({}, None)
        assert isinstance(message_history, MessageHistory)
        assert len(message_history) == 0

    def test_simple_parameters(self):
        """Test with simple string parameters."""
        tool_params = [
            Parameter(name="param1", param_type="string", description="First parameter"),
            Parameter(name="param2", param_type="string", description="Second parameter"),
        ]
        tool_parameters = {"param1": "value1", "param2": "value2"}
        
        message_history = LLMBase.prepare_tool_message_history(tool_parameters, tool_params)
        
        assert isinstance(message_history, MessageHistory)
        assert len(message_history) == 1
        assert message_history[0].role == "user"
        
        # Check that the message contains the parameter names and values
        message_content = message_history[0].content
        assert "You are being called as a tool with the following parameters:" in message_content
        assert "• param1: value1" in message_content
        assert "• param2: value2" in message_content
        assert "Please execute your function based on these parameters." in message_content

    def test_array_parameters(self):
        """Test with array parameters."""
        tool_params = [
            Parameter(name="items", param_type="array", description="List of items"),
        ]
        tool_parameters = {"items": ["item1", "item2", "item3"]}
        
        message_history = LLMBase.prepare_tool_message_history(tool_parameters, tool_params)
        
        assert isinstance(message_history, MessageHistory)
        assert len(message_history) == 1
        
        # Check that the array is formatted correctly
        message_content = message_history[0].content
        assert "• items: item1, item2, item3" in message_content

    def test_object_parameters(self):
        """Test with object parameters."""
        tool_params = [
            Parameter(name="config", param_type="object", description="Configuration object"),
        ]
        tool_parameters = {"config": {"key1": "value1", "key2": "value2"}}
        
        message_history = LLMBase.prepare_tool_message_history(tool_parameters, tool_params)
        
        assert isinstance(message_history, MessageHistory)
        assert len(message_history) == 1
        
        # Check that the object is formatted correctly
        message_content = message_history[0].content
        assert "• config: key1=value1; key2=value2" in message_content

    def test_missing_parameter(self):
        """Test with a missing parameter."""
        with pytest.raises(KeyError):
            tool_params = [
                Parameter(name="param1", param_type="string", description="First parameter"),
                Parameter(name="param2", param_type="string", description="Second parameter"),
            ]
            tool_parameters = {"param1": "value1"}  # param2 is missing

            LLMBase.prepare_tool_message_history(tool_parameters, tool_params)
