from contextlib import contextmanager

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

@pytest.mark.asyncio
@patch("railtracks.execution.execution_strategy.NodeState")
@patch("railtracks.execution.execution_strategy.get_publisher")
async def test_asyncio_execute_binds_scope_manager_and_enters_node_scope(
    mock_get_publisher, mock_node_state, mock_task, mock_publisher
):
    mock_get_publisher.return_value = mock_publisher
    mock_node_state.return_value = "fake-node-state"
    mock_task.invoke = AsyncMock(return_value="completed!")

    calls = []

    class FakeScopeManager:
        @contextmanager
        def enter_node(self, node_id):
            calls.append(("enter_node", node_id))
            yield

    scope_manager = FakeScopeManager()
    mock_task.node.bind_scope_manager = MagicMock()

    strat = AsyncioExecutionStrategy(scope_manager=scope_manager)
    await strat.execute(mock_task)

    mock_task.node.bind_scope_manager.assert_called_once_with(scope_manager)
    assert calls == [("enter_node", "mock-uuid")]

# ============ END AsyncioExecutionStrategy Tests ===============

# ============ START Miscellaneous Structure Tests ===============
def test_task_execution_strategy_base_shutdown():
    # Should work for coverage, is a no-op
    class DummyStrategy(AsyncioExecutionStrategy):
        pass

    strat = DummyStrategy()
    strat.shutdown()  # should be no-op

# ============ END Miscellaneous Structure Tests ===============