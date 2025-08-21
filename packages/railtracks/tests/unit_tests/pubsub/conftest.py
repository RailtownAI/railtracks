import pytest
from unittest.mock import patch
from railtracks.pubsub.publisher import RTPublisher
# ================================== Pub Sub Fixtures ==================================
@pytest.fixture
def dummy_publisher():
    pub = RTPublisher()
    return pub

@pytest.fixture
def logger_patch():
    with patch("railtracks.utils.publisher.logger") as mock_logger:
        yield mock_logger

# ================================== Message Fixtures ==================================
@pytest.fixture
def dummy_node_class():
    class Node:
        def name(self):
            return "MockNode"
    return Node

@pytest.fixture
def dummy_node_state(dummy_node_class):
    class DummyNodeState:
        def __init__(self):
            self.node = dummy_node_class()
        def instantiate(self):
            return self.node
        def __repr__(self):
            return f"DummyNodeState({self.node})"
    return DummyNodeState()

@pytest.fixture
def dummy_exception():
    return Exception("Something went wrong")