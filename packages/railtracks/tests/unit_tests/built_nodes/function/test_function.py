
import functools

import pytest
from railtracks.built_nodes.function.node import (
    CallableAsyncRTFunction,
    CallableSyncRTFunction,
    _function_preserving_metadata,
    _partial_with_resolved_metadata,
    function_node,
)


@pytest.mark.asyncio
async def async_func(x):
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

def test_function_node_with_stray_node_type_attribute_is_rebuilt(mock_function):
    f = mock_function
    setattr(f, "node_type", "AlreadyNodeType")
    node = function_node(f, name="TestFunc")
    assert isinstance(node, CallableSyncRTFunction)
    assert isinstance(node.node_type, type)

def test_function_node_reconversion_is_a_noop_returns_same_object(mock_function):
    node = function_node(mock_function, name="TestFunc")
    again = function_node(node)
    assert again is node

def test_function_node_async_reconversion_is_a_noop_returns_same_object():
    async def my_async_fn(x: int) -> int:
        return x

    node = function_node(my_async_fn)
    again = function_node(node)
    assert again is node

def test_function_node_preserves_name_and_doc():
    def my_fn(x: int) -> int:
        """My docstring."""
        return x

    node = function_node(my_fn)
    assert node.__name__ == "my_fn"
    assert node.__doc__ == "My docstring."

@pytest.mark.asyncio
async def test_function_node_async_preserves_name_and_doc():
    async def my_async_fn(x: int) -> int:
        """My async docstring."""
        return x

    node = function_node(my_async_fn)
    assert isinstance(node, CallableAsyncRTFunction)
    assert node.__name__ == "my_async_fn"
    assert node.__doc__ == "My async docstring."

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


# ---------------------------------------------------------------------------
# Bound methods (issue #1318)
# ---------------------------------------------------------------------------
class _Calculator:
    def add(self, a: int, b: int) -> int:
        """Add two numbers.

        Args:
            a: first addend
            b: second addend
        """
        return a + b

    async def amultiply(self, a: int, b: int) -> int:
        """Multiply two numbers asynchronously.

        Args:
            a: first factor
            b: second factor
        """
        return a * b


def test_function_node_sync_bound_method():
    calc = _Calculator()
    node = function_node(calc.add)
    assert isinstance(node, CallableSyncRTFunction)
    # bound methods already carry the correct metadata
    assert node.__name__ == "add"
    assert node.__doc__.startswith("Add two numbers.")
    tool_info = node.node_type.tool_info()
    assert tool_info.name == "add"
    assert tool_info.detail == "Add two numbers."
    # `self` must not leak into the tool parameters
    assert sorted(p.name for p in tool_info.parameters) == ["a", "b"]


def test_function_node_async_bound_method():
    calc = _Calculator()
    node = function_node(calc.amultiply)
    assert isinstance(node, CallableAsyncRTFunction)
    assert node.__name__ == "amultiply"
    tool_info = node.node_type.tool_info()
    assert sorted(p.name for p in tool_info.parameters) == ["a", "b"]


@pytest.mark.asyncio
async def test_function_node_bound_method_executes():
    import railtracks as rt

    calc = _Calculator()
    add_node = function_node(calc.add)
    amul_node = function_node(calc.amultiply)
    assert await rt.call(add_node, 2, 3) == 5
    assert await rt.call(amul_node, 2, 4) == 8


# ---------------------------------------------------------------------------
# functools.partial (issue #1318)
# ---------------------------------------------------------------------------
def _greet(greeting: str, name: str) -> str:
    """Greet someone.

    Args:
        greeting: the greeting word
        name: who to greet
    """
    return f"{greeting}, {name}!"


async def _apower(base: int, exp: int) -> int:
    """Raise base to exp.

    Args:
        base: the base
        exp: the exponent
    """
    return base**exp


def test_partial_with_resolved_metadata_sources_from_underlying():
    partial = functools.partial(_greet, "Hello")
    resolved = _partial_with_resolved_metadata(partial)
    # metadata comes from the wrapped callable, not the boilerplate partial
    assert resolved.__name__ == "_greet"
    assert resolved.__qualname__ == _greet.__qualname__
    assert resolved.__doc__ == _greet.__doc__
    # the original partial is left untouched
    assert not hasattr(partial, "__name__")
    # the reduced signature is preserved (greeting already bound)
    assert resolved("World") == "Hello, World!"


def test_partial_with_resolved_metadata_unwraps_nested_partials():
    nested = functools.partial(functools.partial(_greet, "Hi"), name="There")
    resolved = _partial_with_resolved_metadata(nested)
    assert resolved.__name__ == "_greet"
    assert resolved.__doc__ == _greet.__doc__


def test_function_node_sync_partial():
    partial = functools.partial(_greet, "Hello")
    node = function_node(partial)
    assert isinstance(node, CallableSyncRTFunction)
    assert node.__name__ == "_greet"
    tool_info = node.node_type.tool_info()
    assert tool_info.name == "_greet"
    assert tool_info.detail == "Greet someone."
    # `greeting` is already bound, so only `name` remains as a tool parameter
    assert [p.name for p in tool_info.parameters] == ["name"]


def test_function_node_async_partial():
    partial = functools.partial(_apower, exp=2)
    node = function_node(partial)
    assert isinstance(node, CallableAsyncRTFunction)
    assert node.__name__ == "_apower"
    tool_info = node.node_type.tool_info()
    assert tool_info.detail == "Raise base to exp."


@pytest.mark.asyncio
async def test_function_node_partial_executes():
    import railtracks as rt

    greet_node = function_node(functools.partial(_greet, "Hello"))
    power_node = function_node(functools.partial(_apower, exp=2))
    assert await rt.call(greet_node, name="World") == "Hello, World!"
    assert await rt.call(power_node, base=3) == 9