import pytest

import railtracks as rt
from railtracks.execution.task import Task


@pytest.mark.asyncio
async def test_invoke_calls_node_wrapped_invoke(mock_node):
    task = Task(request_id="req-1", node=mock_node, arguments=((), {}))
    result = await task.invoke()
    mock_node.wrapped_invoke.assert_awaited_once()
    assert result == "result"

@pytest.mark.asyncio
async def test_invoke_propagates_exception(mock_node):
    mock_node.wrapped_invoke.side_effect = RuntimeError("fail!")
    task = Task(request_id="req-2", node=mock_node, arguments=((), {}))
    with pytest.raises(RuntimeError, match="fail!"):
        await task.invoke()
    mock_node.wrapped_invoke.assert_awaited_once()


def hello_world():
    print("Hello, World!")


HelloWorldNode = rt.function_node(hello_world)


def test_task_invoke():
    hwn = HelloWorldNode()
    task = rt.execution.task.Task(
        node=hwn, request_id="test_request_id", arguments=((), {})
    )

    assert task.node == hwn
    assert task.request_id == "test_request_id"
