"""Integration test for agent_node with instance and class methods as tools."""

import pytest
import railtracks as rt


class Calculator:
    """A simple calculator class for testing different method types."""

    def add_instance(self, a: int, b: int) -> int:
        """Add two numbers using an instance method."""
        return a + b

    @staticmethod
    def add_static(a: int, b: int) -> int:
        """Add two numbers using a static method."""
        return a + b

    @classmethod
    def add_class(cls, a: int, b: int) -> int:
        """Add two numbers using a class method."""
        return a + b


def test_agent_node_with_instance_method():
    """Test that agent_node can be created with instance methods as tools."""
    calculator = Calculator()
    
    # This should not raise an error
    tool_node = rt.function_node(calculator.add_instance)
    
    # Verify the node was created successfully
    assert hasattr(tool_node, "node_type")
    

def test_agent_node_with_class_method():
    """Test that agent_node can be created with class methods as tools."""
    calculator = Calculator()
    
    # This should not raise an error
    tool_node = rt.function_node(calculator.add_class)
    
    # Verify the node was created successfully
    assert hasattr(tool_node, "node_type")


def test_agent_node_with_static_method():
    """Test that agent_node can be created with static methods as tools."""
    calculator = Calculator()
    
    # This should not raise an error
    tool_node = rt.function_node(calculator.add_static)
    
    # Verify the node was created successfully
    assert hasattr(tool_node, "node_type")


def test_agent_node_with_multiple_method_types():
    """Test that agent_node can be created with multiple method types as tools."""
    calculator = Calculator()
    
    # Create tool nodes from all method types
    tool_nodes = [
        rt.function_node(calculator.add_instance),
        rt.function_node(calculator.add_class),
        rt.function_node(calculator.add_static),
    ]
    
    # Verify all nodes were created successfully
    assert len(tool_nodes) == 3
    for tool_node in tool_nodes:
        assert hasattr(tool_node, "node_type")

