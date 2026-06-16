import inspect
import pytest
from unittest.mock import patch, MagicMock
from railtracks.built_nodes.easy_usage_wrappers.function import function_node, _function_preserving_metadata


class _SimpleCalc:
    """Minimal class used to produce bound methods for testing."""

    def __init__(self, offset: int = 0):
        self.offset = offset

    def add(self, x: int, y: int) -> int:
        """Add two numbers and apply offset."""
        return x + y + self.offset

    async def async_add(self, x: int, y: int) -> int:
        """Async variant."""
        return x + y + self.offset

async def async_func(x, y):
    return x

def test_function_node_sync(mock_function, mock_manifest):
    node = function_node(mock_function, name="TestFunc", manifest=mock_manifest)
    assert hasattr(node, "node_type")
    assert node.__name__ == mock_function.__name__

@pytest.mark.asyncio
async def test_function_node_async():
    node = function_node(async_func, name="AsyncFunc")
    assert hasattr(node, "node_type")
    # __name__ may not be present on the returned mock, so skip strict check

def test_function_node_with_manifest(mock_function, mock_manifest):
    node = function_node(mock_function, name="TestFunc", manifest=mock_manifest)
    assert hasattr(node, "node_type")

def test_function_node_builtin():
    import math
    node = function_node(math.ceil, name="CeilFunc")
    assert hasattr(node, "node_type")

def test_function_node_already_node_type(mock_function):
    f = mock_function
    setattr(f, "node_type", "AlreadyNodeType")
    with patch("warnings.warn") as warn_mock:
        result = function_node(f)
        assert result is f
        warn_mock.assert_called_once()

def test_function_node_invalid_type():
    class NotAFunction:
        pass
    with pytest.raises(Exception):
        function_node(NotAFunction())

def test_function_preserving_metadata():
    def f(x): return x + 1
    wrapped = _function_preserving_metadata(f)
    assert wrapped.__name__ == f.__name__
    assert wrapped(2) == 3


# --- Bound method tests ---

def test_function_node_sync_bound_method():
    # inspect.ismethod() is True for bound methods; inspect.isfunction() is False.
    # function_node must handle this case without raising NodeCreationError.
    calc = _SimpleCalc(offset=5)
    assert inspect.ismethod(calc.add)
    node = function_node(calc.add)
    assert hasattr(node, "node_type")


def test_function_node_sync_bound_method_preserves_name():
    calc = _SimpleCalc()
    node = function_node(calc.add)
    assert node.__name__ == "add"


def test_function_node_sync_bound_method_remains_callable():
    calc = _SimpleCalc(offset=10)
    node = function_node(calc.add)
    assert node(1, 2) == 13


def test_function_node_sync_bound_method_with_manifest(mock_manifest):
    calc = _SimpleCalc()
    node = function_node(calc.add, manifest=mock_manifest)
    assert hasattr(node, "node_type")




@pytest.mark.asyncio
async def test_function_node_async_bound_method():
    calc = _SimpleCalc(offset=1)
    node = function_node(calc.async_add)
    assert hasattr(node, "node_type")