import pytest
from railtracks.built_nodes.easy_usage_wrappers.function import function_node

def test_function_node_sync(mock_function, mock_manifest):
    node = function_node(mock_function, name="TestFunc", manifest=mock_manifest)
    # Should have node_type attribute
    assert hasattr(node, "node_type")
    # Should preserve function name
    assert node.__name__ == mock_function.__name__

@pytest.mark.asyncio
async def test_function_node_async():
    async def afunc(x): return x
    node = function_node(afunc, name="AsyncFunc")
    assert hasattr(node, "node_type")
    assert node.__name__ == "afunc"