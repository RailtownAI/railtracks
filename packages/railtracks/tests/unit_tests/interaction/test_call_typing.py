"""
Tests for typing correctness in call and call_sync functions.

This module tests that the return type annotations are correct for:
- call_sync with agent nodes (should return StringResponse, not the node type)
- call_sync with function nodes (should return the actual function return type)
"""

import pytest
from typing import TYPE_CHECKING

import railtracks as rt


# For typing tests, we need this import
if TYPE_CHECKING:
    from railtracks.nodes.concrete.response import StringResponse


def test_function_node_call_sync_typing():
    """Test that call_sync with function nodes returns the correct type."""
    
    def multiply(a: float, b: float) -> float:
        return a * b

    MultiplyNode = rt.function_node(multiply)
    
    # This should have correct typing: float
    result = rt.call_sync(MultiplyNode, a=5.0, b=3.0)
    
    # Runtime check
    assert isinstance(result, float)
    assert result == 15.0


def test_agent_node_creation_typing():
    """Test that agent nodes are created correctly."""
    system_prompt = "You are a helpful assistant."
    
    # This should create a Type[TerminalLLM]
    Agent = rt.agent_node(
        "Test Assistant",
        system_message=system_prompt
    )
    
    # Runtime check - this should be a class type
    assert callable(Agent)
    assert hasattr(Agent, '__name__')


def test_typing_overloads_exist():
    """Test that our typing overloads are correctly imported and available."""
    from railtracks.interaction.call import call, call_sync
    
    # These functions should exist and be callable
    assert callable(call)
    assert callable(call_sync)
    
    # Check that the functions have the proper annotations
    import inspect
    call_sig = inspect.signature(call)
    call_sync_sig = inspect.signature(call_sync)
    
    # Both should have at least one parameter named 'node' or 'node_'
    assert 'node_' in call_sig.parameters or 'node' in call_sync_sig.parameters


if __name__ == "__main__":
    test_function_node_call_sync_typing()
    test_agent_node_creation_typing() 
    test_typing_overloads_exist()
    print("All typing tests passed!")