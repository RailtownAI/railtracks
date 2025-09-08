import pytest
from railtracks.nodes.utils import extract_node_from_function

class DummyAsync:
    node_type = "AsyncNodeType"

class DummySync:
    node_type = "SyncNodeType"

def dummy_func():
    return "sync"

async def dummy_async_func():
    return "async"

def test_extract_node_from_function_with_node_type_sync():
    node_type = extract_node_from_function(DummySync())
    assert node_type == "SyncNodeType"

def test_extract_node_from_function_with_node_type_async():
    node_type = extract_node_from_function(DummyAsync())
    assert node_type == "AsyncNodeType"

# Patch function_node to return an object with node_type for pure function case
import railtracks.nodes.utils
import types

def test_extract_node_from_function_with_pure_function(monkeypatch):
    class FakeNode:
        node_type = "FakeNodeType"
    def fake_function_node(func):
        return FakeNode
    monkeypatch.setattr("railtracks.function_node", fake_function_node)
    node_type = extract_node_from_function(dummy_func)
    assert node_type == "FakeNodeType"

# Also test with async function

def test_extract_node_from_function_with_pure_async_function(monkeypatch):
    class FakeNode:
        node_type = "FakeAsyncNodeType"
    def fake_function_node(func):
        return FakeNode
    monkeypatch.setattr("railtracks.function_node", fake_function_node)
    node_type = extract_node_from_function(dummy_async_func)
    assert node_type == "FakeAsyncNodeType"
