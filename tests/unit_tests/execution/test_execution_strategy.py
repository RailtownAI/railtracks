import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from railtracks.execution.execution_strategy import (
    AsyncioExecutionStrategy,
)
from railtracks.pubsub.messages import RequestSuccess, RequestFailure

# ============ START AsyncioExecutionStrategy Tests ===============

@pytest.mark.asyncio
@patch("railtracks.execution.execution_strategy.NodeState")
@patch("railtracks.execution.execution_strategy.get_publisher")
async def test_asyncio_execute_success(
    mock_get_publisher, mock_node_state, mock_task, mock_publisher
):
    # Arrange
    mock_get_publisher.return_value = mock_publisher
    mock_node_state.return_value = "fake-node-state"
    mock_task.invoke = AsyncMock(return_value="completed!")

    strat = AsyncioExecutionStrategy()

    # Act
    response = await strat.execute(mock_task)

    # Assert
    assert isinstance(response, RequestSuccess)
    assert response.result == "completed!"
    assert response.node_state == "fake-node-state"
    mock_publisher.publish.assert_awaited_once_with(response)

@pytest.mark.asyncio
@patch("railtracks.execution.execution_strategy.NodeState")
@patch("railtracks.execution.execution_strategy.get_publisher")
async def test_asyncio_execute_failure(
    mock_get_publisher, mock_node_state, mock_task, mock_publisher
):
    # Arrange
    mock_get_publisher.return_value = mock_publisher
    mock_node_state.return_value = "nstate"
    mock_task.invoke = AsyncMock(side_effect=ValueError("Bang!"))

    strat = AsyncioExecutionStrategy()

    # Act
    response = await strat.execute(mock_task)

    # Assert
    assert isinstance(response, RequestFailure)
    assert isinstance(response.error, ValueError)
    assert response.node_state == "nstate"
    mock_publisher.publish.assert_awaited_once_with(response)

def test_asyncio_shutdown_is_noop():
    strat = AsyncioExecutionStrategy()
    strat.shutdown()  # Should not throw

# ============ END AsyncioExecutionStrategy Tests ===============

# ============ START Miscellaneous Structure Tests ===============
def test_task_execution_strategy_base_shutdown():
    # Should work for coverage, is a no-op
    class DummyStrategy(AsyncioExecutionStrategy):
        pass

    strat = DummyStrategy()
    strat.shutdown()  # should be no-op

# ============ END Miscellaneous Structure Tests ===============