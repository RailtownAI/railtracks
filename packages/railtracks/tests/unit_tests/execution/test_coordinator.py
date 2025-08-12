
import pytest
from unittest.mock import MagicMock, AsyncMock
from typing import get_args

from railtracks.execution.coordinator import (
    Job, CoordinatorState, Coordinator
)
from railtracks.execution.task import Task
from railtracks.pubsub.messages import (
    RequestSuccess, RequestFailure, RequestCreationFailure, ExecutionConfigurations
)

# ============ START Job Tests ===============
def test_job_create_and_end(mock_task):
    job = Job.create_new(mock_task)
    assert job.status == "opened"
    assert job.request_id == "req-1"
    assert job.start_time is not None
    assert job.end_time is None

    job.end_job("success")
    assert job.status == "closed"
    assert job.result == "success"
    assert job.end_time is not None
def test_job_init_with_none_timestamps():
    """Test that Job.__init__ correctly handles None values for start_time and end_time."""
    job = Job(
        request_id="test-req",
        parent_node_id="parent-1",
        child_node_id="child-1",
        status="opened",
        result=None,
        start_time=None,  # Explicitly testing None value
        end_time=None,    # Explicitly testing None value
    )
    assert job.request_id == "test-req"
    assert job.parent_node_id == "parent-1"
    assert job.child_node_id == "child-1"
    assert job.status == "opened"
    assert job.result is None
    assert job.start_time is None
    assert job.end_time is None
# ============ END Job Tests ===============

# ============ START CoordinatorState Tests ===============
def test_coordinator_state_add_and_end_job(mock_task):
    state = CoordinatorState.empty()
    state.add_job(mock_task)
    assert len(state.job_list) == 1
    assert state.job_list[0].status == "opened"

    state.end_job("req-1", "failure")
    assert state.job_list[0].status == "closed"
    assert state.job_list[0].result == "failure"

def test_coordinator_state_end_job_not_found():
    state = CoordinatorState.empty()
    with pytest.raises(ValueError):
        state.end_job("not-found", "success")
# ============ END CoordinatorState Tests ===============

# ============ START Coordinator Fixtures ===============
@pytest.fixture
def mock_execution_strategy():
    strat = MagicMock()
    strat.execute = AsyncMock(return_value="exec-result")
    strat.shutdown = MagicMock()
    return strat

@pytest.fixture
def all_execution_modes(mock_execution_strategy):
    # Provide all required execution modes
    return {
        mode: mock_execution_strategy
        for mode in get_args(ExecutionConfigurations)
    }

@pytest.fixture
def coordinator(all_execution_modes):
    return Coordinator(execution_modes=all_execution_modes)
# ============ END Coordinator Fixtures ===============

# ============ START Coordinator Async Tests ===============
@pytest.mark.asyncio
async def test_coordinator_submit_adds_job_and_executes(coordinator, mock_task, mock_execution_strategy):
    result = await coordinator.submit(mock_task, list(coordinator.execution_strategy.keys())[0])
    assert result == "exec-result"
    assert len(coordinator.state.job_list) == 1
    mock_execution_strategy.execute.assert_awaited_once_with(mock_task)
# ============ END Coordinator Async Tests ===============

# ============ START Coordinator Message Handling Tests ===============
def test_coordinator_handle_item_success_and_failure(coordinator, mock_task):
    coordinator.state.add_job(mock_task)
    # Simulate success
    msg = RequestSuccess(request_id="req-1", node_state="dummy", result="dummy")
    coordinator.handle_item(msg)
    assert coordinator.state.job_list[0].status == "closed"
    assert coordinator.state.job_list[0].result == "success"

    # Add another job for failure
    mock_task2 = Task(request_id="req-2", node=mock_task.node)
    coordinator.state.add_job(mock_task2)
    msg_fail = RequestFailure(request_id="req-2", node_state="dummy", error=Exception("fail"))
    coordinator.handle_item(msg_fail)
    assert coordinator.state.job_list[1].status == "closed"
    assert coordinator.state.job_list[1].result == "failure"

def test_coordinator_handle_item_creation_failure_does_nothing(coordinator, mock_task):
    coordinator.state.add_job(mock_task)
    msg = RequestCreationFailure(request_id="req-1", error=Exception("fail"))
    coordinator.handle_item(msg)
    # Should not close the job
    assert coordinator.state.job_list[0].status == "opened"
# ============ END Coordinator Message Handling Tests ===============

# ============ START Coordinator Shutdown Tests ===============
def test_coordinator_shutdown_calls_all_strategies(coordinator, mock_execution_strategy):
    coordinator.shutdown()
    for strat in coordinator.execution_strategy.values():
        strat.shutdown.assert_called_once()
# ============ END Coordinator Shutdown Tests ===============