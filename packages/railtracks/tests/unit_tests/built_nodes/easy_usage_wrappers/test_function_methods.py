"""Tests for function_node with instance methods, class methods, and static methods."""

import pytest
from railtracks.built_nodes.easy_usage_wrappers.function import function_node


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


class AsyncCalculator:
    """An async calculator class for testing async method types."""

    async def add_instance(self, a: int, b: int) -> int:
        """Add two numbers using an async instance method."""
        return a + b

    @staticmethod
    async def add_static(a: int, b: int) -> int:
        """Add two numbers using an async static method."""
        return a + b

    @classmethod
    async def add_class(cls, a: int, b: int) -> int:
        """Add two numbers using an async class method."""
        return a + b


def test_function_node_instance_method():
    """Test that function_node works with instance methods."""
    calculator = Calculator()
    node = function_node(calculator.add_instance, name="AddInstance")
    assert hasattr(node, "node_type")
    assert node.__name__ == "add_instance"


def test_function_node_static_method():
    """Test that function_node works with static methods."""
    calculator = Calculator()
    node = function_node(calculator.add_static, name="AddStatic")
    assert hasattr(node, "node_type")
    assert node.__name__ == "add_static"


def test_function_node_class_method():
    """Test that function_node works with class methods."""
    calculator = Calculator()
    node = function_node(calculator.add_class, name="AddClass")
    assert hasattr(node, "node_type")
    assert node.__name__ == "add_class"


@pytest.mark.asyncio
async def test_function_node_async_instance_method():
    """Test that function_node works with async instance methods."""
    calculator = AsyncCalculator()
    node = function_node(calculator.add_instance, name="AsyncAddInstance")
    assert hasattr(node, "node_type")
    assert node.__name__ == "add_instance"


@pytest.mark.asyncio
async def test_function_node_async_static_method():
    """Test that function_node works with async static methods."""
    calculator = AsyncCalculator()
    node = function_node(calculator.add_static, name="AsyncAddStatic")
    assert hasattr(node, "node_type")
    assert node.__name__ == "add_static"


@pytest.mark.asyncio
async def test_function_node_async_class_method():
    """Test that function_node works with async class methods."""
    calculator = AsyncCalculator()
    node = function_node(calculator.add_class, name="AsyncAddClass")
    assert hasattr(node, "node_type")
    assert node.__name__ == "add_class"


def test_function_node_list_of_methods():
    """Test that function_node works with a list containing different method types."""
    calculator = Calculator()
    nodes = function_node(
        [
            calculator.add_instance,
            calculator.add_static,
            calculator.add_class,
        ]
    )
    assert len(nodes) == 3
    for node in nodes:
        assert hasattr(node, "node_type")
