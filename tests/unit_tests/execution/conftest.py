import pytest
from unittest.mock import AsyncMock, MagicMock
from railtracks.execution.task import Task


@pytest.fixture
def mock_node():
    node = AsyncMock()
    node.uuid = "mock-uuid"
    node.tracked_invoke = AsyncMock(return_value="result")
    return node


@pytest.fixture
def mock_task(mock_node):
    return Task(request_id="req-1", node=mock_node)


@pytest.fixture
def mock_execution_strategy():
    strat = MagicMock()
    strat.execute = AsyncMock(return_value="exec-result")
    strat.shutdown = MagicMock()
    return strat


@pytest.fixture
def mock_publisher():
    publisher = MagicMock()
    publisher.publish = AsyncMock()
    return publisher
