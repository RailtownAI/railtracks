import pytest
from unittest.mock import MagicMock, patch
from uuid import UUID

from railtracks.evaluation.runners._evaluate import evaluate
from railtracks.evaluation.evaluators.evaluator import Evaluator
from railtracks.evaluation.result import EvaluatorResult
from railtracks.utils.point import AgentDataPoint
from railtracks.evaluation.data.evaluation_dataset import EvaluationDataset


# ================= Test Evaluator Implementations =================


class MockEvaluator(Evaluator):
    """Mock evaluator for testing purposes."""
    
    def __init__(self, name_suffix=""):
        super().__init__()
        self.name_suffix = name_suffix
        self.run_called = False
        self.run_call_count = 0
    
    def run(self, data: list[AgentDataPoint]) -> EvaluatorResult:
        """Mock run method that tracks calls."""
        self.run_called = True
        self.run_call_count += 1
        
        agent_name = data[0].agent_name if data else "unknown"
        
        return EvaluatorResult(
            evaluator_name=f"MockEvaluator{self.name_suffix}",
            agent_name=agent_name,
            evaluator_id=self.id,
            metrics=[],
            results=[],
        )


# ================= Input Type Tests =================


def test_evaluate_with_single_data_point():
    """Test evaluate with a single AgentDataPoint."""
    data_point = AgentDataPoint(
        agent_name="agent1",
        agent_input={"query": "test"},
        agent_output="result"
    )
    
    evaluator = MockEvaluator()
    results = evaluate(data=data_point, evaluators=[evaluator])
    
    assert len(results) == 1
    assert evaluator.run_called
    assert ("agent1", evaluator.id) in results


def test_evaluate_with_list_of_data_points():
    """Test evaluate with a list of AgentDataPoints."""
    data_points = [
        AgentDataPoint(
            agent_name="agent1",
            agent_input={"query": "test1"},
            agent_output="result1"
        ),
        AgentDataPoint(
            agent_name="agent1",
            agent_input={"query": "test2"},
            agent_output="result2"
        )
    ]
    
    evaluator = MockEvaluator()
    results = evaluate(data=data_points, evaluators=[evaluator])
    
    assert len(results) == 1
    assert evaluator.run_called
    assert ("agent1", evaluator.id) in results


def test_evaluate_with_evaluation_dataset(raw_json_file):
    """Test evaluate with an EvaluationDataset."""
    dataset = EvaluationDataset(path=str(raw_json_file))
    
    evaluator = MockEvaluator()
    results = evaluate(data=dataset, evaluators=[evaluator])
    
    # Dataset has 2 agents (agent1 and agent2)
    assert len(results) == 2
    assert evaluator.run_called


def test_evaluate_with_invalid_data_type():
    """Test evaluate raises ValueError for invalid data type."""
    evaluator = MockEvaluator()
    
    with pytest.raises(ValueError, match="Data must be an EvaluationDataset"):
        evaluate(data="invalid", evaluators=[evaluator])


def test_evaluate_with_list_containing_invalid_items():
    """Test evaluate handles list with invalid items gracefully."""
    data_points = [
        AgentDataPoint(
            agent_name="agent1",
            agent_input={"query": "test"},
            agent_output="result"
        ),
        "invalid_item",
        AgentDataPoint(
            agent_name="agent1",
            agent_input={"query": "test2"},
            agent_output="result2"
        )
    ]
    
    evaluator = MockEvaluator()
    results = evaluate(data=data_points, evaluators=[evaluator])
    
    # Should process only valid data points
    assert len(results) == 1


# ================= Multiple Evaluators Tests =================


def test_evaluate_with_multiple_evaluators():
    """Test evaluate with multiple evaluators."""
    data_point = AgentDataPoint(
        agent_name="agent1",
        agent_input={"query": "test"},
        agent_output="result"
    )
    
    evaluator1 = MockEvaluator(name_suffix="1")
    evaluator2 = MockEvaluator(name_suffix="2")
    
    results = evaluate(data=data_point, evaluators=[evaluator1, evaluator2])
    
    assert len(results) == 2
    assert evaluator1.run_called
    assert evaluator2.run_called
    assert ("agent1", evaluator1.id) in results
    assert ("agent1", evaluator2.id) in results


def test_evaluate_with_empty_evaluators_list():
    """Test evaluate with empty evaluators list."""
    data_point = AgentDataPoint(
        agent_name="agent1",
        agent_input={"query": "test"},
        agent_output="result"
    )
    
    results = evaluate(data=data_point, evaluators=[])
    
    assert len(results) == 0


# ================= Multiple Agents Tests =================


def test_evaluate_with_multiple_agents():
    """Test evaluate with data points from multiple agents."""
    data_points = [
        AgentDataPoint(
            agent_name="agent1",
            agent_input={"query": "test1"},
            agent_output="result1"
        ),
        AgentDataPoint(
            agent_name="agent2",
            agent_input={"query": "test2"},
            agent_output="result2"
        )
    ]
    
    evaluator = MockEvaluator()
    results = evaluate(data=data_points, evaluators=[evaluator])
    
    # Should have results for both agents
    assert len(results) == 2
    assert ("agent1", evaluator.id) in results
    assert ("agent2", evaluator.id) in results


def test_evaluate_groups_data_points_by_agent():
    """Test that data points are correctly grouped by agent."""
    data_points = [
        AgentDataPoint(
            agent_name="agent1",
            agent_input={"query": "test1"},
            agent_output="result1"
        ),
        AgentDataPoint(
            agent_name="agent1",
            agent_input={"query": "test2"},
            agent_output="result2"
        ),
        AgentDataPoint(
            agent_name="agent2",
            agent_input={"query": "test3"},
            agent_output="result3"
        )
    ]
    
    evaluator = MockEvaluator()
    results = evaluate(data=data_points, evaluators=[evaluator])
    
    # Evaluator should be called once per agent (2 times total)
    assert evaluator.run_call_count == 2


def test_evaluate_with_multiple_agents_and_evaluators(sample_data_points):
    """Test evaluate with multiple agents and multiple evaluators."""
    evaluator1 = MockEvaluator(name_suffix="1")
    evaluator2 = MockEvaluator(name_suffix="2")
    
    results = evaluate(data=sample_data_points, evaluators=[evaluator1, evaluator2])
    
    # sample_data_points has 2 agents, 2 evaluators = 4 results
    assert len(results) == 4
    assert ("agent1", evaluator1.id) in results
    assert ("agent1", evaluator2.id) in results
    assert ("agent2", evaluator1.id) in results
    assert ("agent2", evaluator2.id) in results


# ================= Return Value Tests =================


def test_evaluate_return_structure():
    """Test evaluate returns correct dictionary structure."""
    data_point = AgentDataPoint(
        agent_name="agent1",
        agent_input={"query": "test"},
        agent_output="result"
    )
    
    evaluator = MockEvaluator()
    results = evaluate(data=data_point, evaluators=[evaluator])
    
    # Check key structure
    key = ("agent1", evaluator.id)
    assert key in results
    
    # Check value is EvaluatorResult
    assert isinstance(results[key], EvaluatorResult)


def test_evaluate_result_contains_correct_agent_name():
    """Test that results contain correct agent name."""
    data_point = AgentDataPoint(
        agent_name="my_agent",
        agent_input={"query": "test"},
        agent_output="result"
    )
    
    evaluator = MockEvaluator()
    results = evaluate(data=data_point, evaluators=[evaluator])
    
    result = results[("my_agent", evaluator.id)]
    assert result.agent_name == "my_agent"


def test_evaluate_result_contains_correct_evaluator_id():
    """Test that results contain correct evaluator ID."""
    data_point = AgentDataPoint(
        agent_name="agent1",
        agent_input={"query": "test"},
        agent_output="result"
    )
    
    evaluator = MockEvaluator()
    results = evaluate(data=data_point, evaluators=[evaluator])
    
    result = results[("agent1", evaluator.id)]
    assert result.evaluator_id == evaluator.id


def test_evaluate_preserves_all_evaluator_results():
    """Test that all evaluator results are preserved in return value."""
    data_points = [
        AgentDataPoint(
            agent_name="agent1",
            agent_input={"query": "test1"},
            agent_output="result1"
        ),
        AgentDataPoint(
            agent_name="agent2",
            agent_input={"query": "test2"},
            agent_output="result2"
        )
    ]
    
    evaluators = [MockEvaluator(name_suffix=str(i)) for i in range(3)]
    
    results = evaluate(data=data_points, evaluators=evaluators)
    
    # 2 agents * 3 evaluators = 6 results
    assert len(results) == 6
    
    # Verify all combinations exist
    for agent_name in ["agent1", "agent2"]:
        for evaluator in evaluators:
            assert (agent_name, evaluator.id) in results


# ================= Edge Cases =================


def test_evaluate_with_empty_data_list():
    """Test evaluate with empty data list."""
    evaluator = MockEvaluator()
    results = evaluate(data=[], evaluators=[evaluator])
    
    # Should return empty results
    assert len(results) == 0
    assert not evaluator.run_called


def test_evaluate_with_single_agent_multiple_data_points():
    """Test evaluate correctly handles multiple data points for one agent."""
    data_points = [
        AgentDataPoint(
            agent_name="agent1",
            agent_input={"query": f"test{i}"},
            agent_output=f"result{i}"
        )
        for i in range(5)
    ]
    
    evaluator = MockEvaluator()
    results = evaluate(data=data_points, evaluators=[evaluator])
    
    assert len(results) == 1
    assert evaluator.run_call_count == 1  # Called once with all data points


def test_evaluate_dataset_with_multiple_agents(dataset_json_file):
    """Test evaluate with dataset containing multiple agents."""
    dataset = EvaluationDataset(path=str(dataset_json_file))
    
    evaluator1 = MockEvaluator(name_suffix="1")
    evaluator2 = MockEvaluator(name_suffix="2")
    
    results = evaluate(data=dataset, evaluators=[evaluator1, evaluator2])
    
    # Dataset has agent1 and agent2, with 2 evaluators = 4 results
    assert len(results) == 4


def test_evaluate_calls_each_evaluator_independently():
    """Test that each evaluator is called independently."""
    data_point = AgentDataPoint(
        agent_name="agent1",
        agent_input={"query": "test"},
        agent_output="result"
    )
    
    evaluator1 = MockEvaluator(name_suffix="1")
    evaluator2 = MockEvaluator(name_suffix="2")
    
    results = evaluate(data=data_point, evaluators=[evaluator1, evaluator2])
    
    # Both evaluators should be called
    assert evaluator1.run_call_count == 1
    assert evaluator2.run_call_count == 1
    
    # Results should be independent
    result1 = results[("agent1", evaluator1.id)]
    result2 = results[("agent1", evaluator2.id)]
    
    assert result1.evaluator_id != result2.evaluator_id


# ================= Data Conversion Tests =================


def test_evaluate_converts_single_datapoint_to_dict():
    """Test that single data point is converted to dict structure."""
    data_point = AgentDataPoint(
        agent_name="agent1",
        agent_input={"query": "test"},
        agent_output="result"
    )
    
    evaluator = MockEvaluator()
    
    # Patch the evaluator's run to capture what it receives
    original_run = evaluator.run
    received_data = []
    
    def capture_run(data):
        received_data.extend(data)
        return original_run(data)
    
    evaluator.run = capture_run
    
    evaluate(data=data_point, evaluators=[evaluator])
    
    # Should receive data as a list
    assert len(received_data) == 1
    assert received_data[0] == data_point


def test_evaluate_groups_list_by_agent_name():
    """Test that list is properly grouped by agent_name."""
    data_points = [
        AgentDataPoint(
            agent_name="agent1",
            agent_input={"query": "test1"},
            agent_output="result1"
        ),
        AgentDataPoint(
            agent_name="agent2",
            agent_input={"query": "test2"},
            agent_output="result2"
        ),
        AgentDataPoint(
            agent_name="agent1",
            agent_input={"query": "test3"},
            agent_output="result3"
        )
    ]
    
    evaluator = MockEvaluator()
    
    # Track received data
    received_calls = []
    original_run = evaluator.run
    
    def capture_run(data):
        received_calls.append((data[0].agent_name, len(data)))
        return original_run(data)
    
    evaluator.run = capture_run
    
    evaluate(data=data_points, evaluators=[evaluator])
    
    # Should be called twice (once per agent)
    assert len(received_calls) == 2
    
    # Check that agent1 received 2 data points
    agent1_call = next(call for call in received_calls if call[0] == "agent1")
    assert agent1_call[1] == 2
    
    # Check that agent2 received 1 data point
    agent2_call = next(call for call in received_calls if call[0] == "agent2")
    assert agent2_call[1] == 1


def test_evaluate_uses_dataset_data_points_dict():
    """Test that EvaluationDataset is converted using data_points_dict."""
    # Create a simple dataset
    data_points = [
        AgentDataPoint(
            agent_name="agent1",
            agent_input={"query": "test"},
            agent_output="result"
        )
    ]
    
    # Create mock dataset
    mock_dataset = MagicMock(spec=EvaluationDataset)
    mock_dataset.data_points_dict = {"agent1": data_points}
    
    evaluator = MockEvaluator()
    results = evaluate(data=mock_dataset, evaluators=[evaluator])
    
    assert len(results) == 1
    assert ("agent1", evaluator.id) in results


# ================= Integration Tests =================


def test_evaluate_full_workflow_with_real_data(sample_data_points):
    """Test full workflow with realistic data."""
    evaluator1 = MockEvaluator(name_suffix="_accuracy")
    evaluator2 = MockEvaluator(name_suffix="_quality")
    
    results = evaluate(
        data=sample_data_points,
        evaluators=[evaluator1, evaluator2]
    )
    
    # Verify all expected results are present
    assert len(results) == 4  # 2 agents * 2 evaluators
    
    # Verify result structure
    for key, result in results.items():
        agent_name, evaluator_id = key
        assert isinstance(agent_name, str)
        assert isinstance(evaluator_id, UUID)
        assert isinstance(result, EvaluatorResult)
        assert result.agent_name == agent_name
        assert result.evaluator_id == evaluator_id


def test_evaluate_with_mixed_data_sources():
    """Test evaluate works consistently across different input types."""
    # Create the same data in different formats
    data_point = AgentDataPoint(
        agent_name="agent1",
        agent_input={"query": "test"},
        agent_output="result"
    )
    
    evaluator1 = MockEvaluator()
    evaluator2 = MockEvaluator()
    evaluator3 = MockEvaluator()
    
    # Test with single data point
    result1 = evaluate(data=data_point, evaluators=[evaluator1])
    
    # Test with list
    result2 = evaluate(data=[data_point], evaluators=[evaluator2])
    
    # Both should produce the same structure
    assert len(result1) == 1
    assert len(result2) == 1


def test_evaluate_evaluator_receives_correct_data():
    """Test that evaluators receive the correct subset of data."""
    data_points = [
        AgentDataPoint(
            agent_name="agent1",
            agent_input={"query": "agent1_test1"},
            agent_output="result1"
        ),
        AgentDataPoint(
            agent_name="agent1",
            agent_input={"query": "agent1_test2"},
            agent_output="result2"
        ),
        AgentDataPoint(
            agent_name="agent2",
            agent_input={"query": "agent2_test"},
            agent_output="result3"
        )
    ]
    
    # Create evaluator that validates received data
    class ValidatingEvaluator(Evaluator):
        def __init__(self):
            super().__init__()
            self.received_data = {}
        
        def run(self, data: list[AgentDataPoint]) -> EvaluatorResult:
            agent_name = data[0].agent_name
            self.received_data[agent_name] = data
            
            return EvaluatorResult(
                evaluator_name="ValidatingEvaluator",
                agent_name=agent_name,
                evaluator_id=self.id,
                metrics=[],
                results=[],
            )
    
    evaluator = ValidatingEvaluator()
    evaluate(data=data_points, evaluators=[evaluator])
    
    # Verify agent1 received 2 data points
    assert len(evaluator.received_data["agent1"]) == 2
    assert all(dp.agent_name == "agent1" for dp in evaluator.received_data["agent1"])
    
    # Verify agent2 received 1 data point
    assert len(evaluator.received_data["agent2"]) == 1
    assert evaluator.received_data["agent2"][0].agent_name == "agent2"
