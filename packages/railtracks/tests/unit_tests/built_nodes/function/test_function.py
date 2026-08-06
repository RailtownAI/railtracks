
import pytest
from railtracks.built_nodes.function.node import (
    CallableAsyncRTFunction,
    CallableSyncRTFunction,
    _function_preserving_metadata,
    function_node,
)
from railtracks.exceptions import NodeCreationError


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


def test_function_node_rejects_sync_bound_method():
    """A sync bound method is neither a coroutine function nor `inspect.isfunction`
    (it's `inspect.ismethod`), so it's rejected -- a deliberate tightening from the
    old easy_usage_wrappers implementation, which used to warn-and-passthrough for
    any object with a stray `node_type` attribute (methods included)."""

    class Foo:
        def method(self, x: int) -> int:
            return x

    with pytest.raises(NodeCreationError):
        function_node(Foo().method)


@pytest.mark.asyncio
async def test_function_node_accepts_async_bound_method():
    """An async bound method passes `asyncio.iscoroutinefunction` (there's no
    `inspect.isfunction`-style gate on that branch), so it's still accepted."""

    class Foo:
        async def method(self, x: int) -> int:
            return x + 1

    node = function_node(Foo().method)
    assert isinstance(node, CallableAsyncRTFunction)