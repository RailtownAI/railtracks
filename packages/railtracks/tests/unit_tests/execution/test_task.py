import pytest
from unittest.mock import AsyncMock, patch

import railtracks as rt
from railtracks.execution.task import Task


@patch("railtracks.execution.task.update_parent_id")
@patch("railtracks.execution.task.get_run_id")
@pytest.mark.asyncio
async def test_invoke_calls_update_and_node_invoke(mock_get_run_id, mock_update_parent_id, mock_node):
    task = Task(request_id="req-1", node=mock_node)
    result = await task.invoke()
    mock_update_parent_id.assert_called_once_with("mock-uuid")
    mock_node.tracked_invoke.assert_awaited_once()
    assert result == "result"

@patch("railtracks.execution.task.get_run_id")
@patch("railtracks.execution.task.update_parent_id")
@pytest.mark.asyncio
async def test_invoke_propagates_exception(mock_update_parent_id, mock_get_run_id, mock_node):
    mock_node.tracked_invoke.side_effect = RuntimeError("fail!")
    task = Task(request_id="req-2", node=mock_node)
    with pytest.raises(RuntimeError, match="fail!"):
        await task.invoke()
    mock_update_parent_id.assert_called_once_with("mock-uuid")
    mock_node.tracked_invoke.assert_awaited_once()


def hello_world():
    print("Hello, World!")


HelloWorldNode = rt.function_node(hello_world)


def test_task_invoke():
    hwn = HelloWorldNode()
    task = rt.execution.task.Task(node=hwn, request_id="test_request_id")

    assert task.node == hwn
    assert task.request_id == "test_request_id"
