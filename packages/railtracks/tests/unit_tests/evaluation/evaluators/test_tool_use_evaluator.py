import pytest
from uuid import UUID

from railtracks.evaluation.evaluators.tool_use_evaluator import (
    ToolUseEvaluator,
    ToolFrequency,
    ToolFailureRate,
)
from railtracks.evaluation.result import EvaluatorResult
from railtracks.utils.point import AgentDataPoint
from railtracks.evaluation.data.evaluation_dataset import EvaluationDataset


# ================= Metric Class Tests =================


def test_tool_frequency_metric_creation():
    """Test ToolFrequency metric creation."""
    metric = ToolFrequency(name="test_tool_frequency")
    
    assert metric.name == "test_tool_frequency"
    assert metric.min_value == 0
    assert metric.max_value is None


def test_tool_frequency_with_custom_min():
    """Test ToolFrequency with custom min_value."""
    metric = ToolFrequency(name="test_tool", min_value=5)
    
    assert metric.min_value == 5


def test_tool_failure_rate_metric_creation():
    """Test ToolFailureRate metric creation."""
    metric = ToolFailureRate(name="test_failure_rate")
    
    assert metric.name == "test_failure_rate"
    assert metric.min_value == 0.0
    assert metric.max_value == 1.0


def test_tool_failure_rate_with_custom_bounds():
    """Test ToolFailureRate with custom min/max values."""
    metric = ToolFailureRate(
        name="test_failure",
        min_value=0.1,
        max_value=0.9
    )
    
    assert metric.min_value == 0.1
    assert metric.max_value == 0.9


# ================= Initialization Tests =================


def test_tool_use_evaluator_initialization():
    """Test ToolUseEvaluator initialization."""
    evaluator = ToolUseEvaluator()
    
    assert evaluator.metrics == []
    assert evaluator.results == []
    assert evaluator.name == "ToolUseEvaluator"
    assert isinstance(evaluator.id, UUID)


def test_tool_use_evaluator_inherits_from_evaluator():
    """Test that ToolUseEvaluator properly inherits from Evaluator."""
    evaluator = ToolUseEvaluator()
    
    assert hasattr(evaluator, "name")
    assert hasattr(evaluator, "id")
    assert hasattr(evaluator, "config_hash")
    assert hasattr(evaluator, "run")


# ================= Helper Methods Tests =================


def test_retrieve_tool_stats_with_single_tool():
    """Test _retrieve_tool_stats with a single tool invocation."""
    evaluator = ToolUseEvaluator()
    
    data_point = AgentDataPoint(
        agent_name="test_agent",
        agent_input={"query": "test"},
        agent_output="result",
        agent_internals={
            "tool_invocations": [
                {"name": "search_tool", "result": "Success"}
            ]
        }
    )
    
    evaluator._retrieve_tool_stats([data_point])
    
    assert len(evaluator.metrics) == 2  # frequency and failure rate
    assert len(evaluator.results) == 2


def test_retrieve_tool_stats_with_multiple_tools():
    """Test _retrieve_tool_stats with multiple tool invocations."""
    evaluator = ToolUseEvaluator()
    
    data_point = AgentDataPoint(
        agent_name="test_agent",
        agent_input={"query": "test"},
        agent_output="result",
        agent_internals={
            "tool_invocations": [
                {"name": "search_tool", "result": "Success"},
                {"name": "calculator", "result": "Success"},
                {"name": "search_tool", "result": "Success"},
            ]
        }
    )
    
    evaluator._retrieve_tool_stats([data_point])
    
    # 2 metrics per tool (frequency + failure rate) = 4 total
    assert len(evaluator.metrics) == 4
    assert len(evaluator.results) == 4


def test_retrieve_tool_stats_with_tool_failure():
    """Test _retrieve_tool_stats correctly counts tool failures."""
    evaluator = ToolUseEvaluator()
    
    data_point = AgentDataPoint(
        agent_name="test_agent",
        agent_input={"query": "test"},
        agent_output="result",
        agent_internals={
            "tool_invocations": [
                {"name": "search_tool", "result": "Success"},
                {"name": "search_tool", "result": "Exception message: error"},
                {"name": "search_tool", "result": "Success"},
            ]
        }
    )
    
    evaluator._retrieve_tool_stats([data_point])
    
    # Find the failure rate result
    failure_rate_result = next(
        r for r in evaluator.results if "failure_rate" in r.metric_name
    )
    
    assert failure_rate_result.value == pytest.approx(1/3)


def test_retrieve_tool_stats_with_all_failures():
    """Test _retrieve_tool_stats when all tool invocations fail."""
    evaluator = ToolUseEvaluator()
    
    data_point = AgentDataPoint(
        agent_name="test_agent",
        agent_input={"query": "test"},
        agent_output="result",
        agent_internals={
            "tool_invocations": [
                {"name": "broken_tool", "result": "Exception message: error 1"},
                {"name": "broken_tool", "result": "Exception message: error 2"},
            ]
        }
    )
    
    evaluator._retrieve_tool_stats([data_point])
    
    failure_rate_result = next(
        r for r in evaluator.results if "failure_rate" in r.metric_name
    )
    
    assert failure_rate_result.value == 1.0


def test_retrieve_tool_stats_with_no_failures():
    """Test _retrieve_tool_stats when no tools fail."""
    evaluator = ToolUseEvaluator()
    
    data_point = AgentDataPoint(
        agent_name="test_agent",
        agent_input={"query": "test"},
        agent_output="result",
        agent_internals={
            "tool_invocations": [
                {"name": "reliable_tool", "result": "Success"},
                {"name": "reliable_tool", "result": "Success"},
            ]
        }
    )
    
    evaluator._retrieve_tool_stats([data_point])
    
    failure_rate_result = next(
        r for r in evaluator.results if "failure_rate" in r.metric_name
    )
    
    assert failure_rate_result.value == 0.0


def test_retrieve_tool_stats_with_missing_internals():
    """Test _retrieve_tool_stats handles missing agent_internals gracefully."""
    evaluator = ToolUseEvaluator()
    
    data_point = AgentDataPoint(
        agent_name="test_agent",
        agent_input={"query": "test"},
        agent_output="result",
        agent_internals=None
    )
    
    evaluator._retrieve_tool_stats([data_point])
    
    # Should handle gracefully without errors
    assert len(evaluator.metrics) == 0
    assert len(evaluator.results) == 0


def test_retrieve_tool_stats_with_empty_tool_invocations():
    """Test _retrieve_tool_stats with empty tool_invocations list."""
    evaluator = ToolUseEvaluator()
    
    data_point = AgentDataPoint(
        agent_name="test_agent",
        agent_input={"query": "test"},
        agent_output="result",
        agent_internals={"tool_invocations": []}
    )
    
    evaluator._retrieve_tool_stats([data_point])
    
    assert len(evaluator.metrics) == 0
    assert len(evaluator.results) == 0


def test_retrieve_tool_stats_aggregates_across_data_points():
    """Test _retrieve_tool_stats aggregates stats across multiple data points."""
    evaluator = ToolUseEvaluator()
    
    data_points = [
        AgentDataPoint(
            agent_name="test_agent",
            agent_input={"query": "test1"},
            agent_output="result1",
            agent_internals={
                "tool_invocations": [
                    {"name": "search_tool", "result": "Success"}
                ]
            }
        ),
        AgentDataPoint(
            agent_name="test_agent",
            agent_input={"query": "test2"},
            agent_output="result2",
            agent_internals={
                "tool_invocations": [
                    {"name": "search_tool", "result": "Success"},
                    {"name": "search_tool", "result": "Exception message: error"}
                ]
            }
        )
    ]
    
    evaluator._retrieve_tool_stats(data_points)
    
    # Find usage count result
    usage_count_result = next(
        r for r in evaluator.results if "usage_count" in r.metric_name
    )
    
    assert usage_count_result.value == 3  # Total uses across both data points


# ================= Run Method Tests =================


def test_run_with_single_data_point():
    """Test run method with a single data point."""
    evaluator = ToolUseEvaluator()
    
    data_point = AgentDataPoint(
        agent_name="test_agent",
        agent_input={"query": "test"},
        agent_output="result",
        agent_internals={
            "tool_invocations": [
                {"name": "search_tool", "result": "Success"}
            ]
        }
    )
    
    result = evaluator.run([data_point])
    
    assert isinstance(result, EvaluatorResult)
    assert result.evaluator_name == "ToolUseEvaluator"
    assert result.agent_name == "test_agent"
    assert result.evaluator_id == evaluator.id
    assert len(result.metrics) == 2
    assert len(result.results) == 2


def test_run_with_list_of_data_points():
    """Test run method with a list of data points."""
    evaluator = ToolUseEvaluator()
    
    data_points = [
        AgentDataPoint(
            agent_name="test_agent",
            agent_input={"query": "test1"},
            agent_output="result1",
            agent_internals={
                "tool_invocations": [
                    {"name": "tool_a", "result": "Success"}
                ]
            }
        ),
        AgentDataPoint(
            agent_name="test_agent",
            agent_input={"query": "test2"},
            agent_output="result2",
            agent_internals={
                "tool_invocations": [
                    {"name": "tool_b", "result": "Success"}
                ]
            }
        )
    ]
    
    result = evaluator.run(data_points)
    
    assert isinstance(result, EvaluatorResult)
    assert len(result.metrics) == 4  # 2 tools * 2 metrics each


def test_run_with_evaluation_dataset(tmp_path):
    """Test run method accepts EvaluationDataset."""
    # Create a dataset
    data_point = AgentDataPoint(
        agent_name="test_agent",
        agent_input={"query": "test"},
        agent_output="result",
        agent_internals={
            "tool_invocations": [
                {"name": "search_tool", "result": "Success"}
            ]
        }
    )
    
    # Create JSON file
    import json
    file_path = tmp_path / "data.json"
    with open(file_path, "w") as f:
        json.dump([data_point.model_dump(mode="json")], f)
    
    dataset = EvaluationDataset(path=str(file_path))
    
    evaluator = ToolUseEvaluator()
    result = evaluator.run(dataset)
    
    assert isinstance(result, EvaluatorResult)


def test_run_sets_agent_name():
    """Test run method sets agent name from data points."""
    evaluator = ToolUseEvaluator()
    
    data_point = AgentDataPoint(
        agent_name="my_agent",
        agent_input={"query": "test"},
        agent_output="result",
        agent_internals={
            "tool_invocations": [
                {"name": "tool", "result": "Success"}
            ]
        }
    )
    
    result = evaluator.run([data_point])
    
    assert result.agent_name == "my_agent"


def test_run_creates_correct_metric_names():
    """Test run creates metrics with correct naming convention."""
    evaluator = ToolUseEvaluator()
    
    data_point = AgentDataPoint(
        agent_name="test_agent",
        agent_input={"query": "test"},
        agent_output="result",
        agent_internals={
            "tool_invocations": [
                {"name": "search_tool", "result": "Success"}
            ]
        }
    )
    
    result = evaluator.run([data_point])
    
    metric_names = [m.name for m in result.metrics]
    
    assert "(search_tool)_failure_rate" in metric_names
    assert "(search_tool)_usage_count" in metric_names


def test_run_creates_metric_results_with_correct_ids():
    """Test that metric results reference correct metric IDs."""
    evaluator = ToolUseEvaluator()
    
    data_point = AgentDataPoint(
        agent_name="test_agent",
        agent_input={"query": "test"},
        agent_output="result",
        agent_internals={
            "tool_invocations": [
                {"name": "tool", "result": "Success"}
            ]
        }
    )
    
    result = evaluator.run([data_point])
    
    # Each metric result should reference a metric by ID
    for metric_result in result.results:
        assert isinstance(metric_result.metric_id, UUID)


# ================= Integration Tests =================


def test_full_workflow_with_multiple_tools():
    """Test full workflow with multiple tools and mixed success/failure."""
    evaluator = ToolUseEvaluator()
    
    data_points = [
        AgentDataPoint(
            agent_name="test_agent",
            agent_input={"query": "test1"},
            agent_output="result1",
            agent_internals={
                "tool_invocations": [
                    {"name": "search", "result": "Success"},
                    {"name": "calculator", "result": "Success"},
                ]
            }
        ),
        AgentDataPoint(
            agent_name="test_agent",
            agent_input={"query": "test2"},
            agent_output="result2",
            agent_internals={
                "tool_invocations": [
                    {"name": "search", "result": "Exception message: timeout"},
                    {"name": "calculator", "result": "Success"},
                ]
            }
        )
    ]
    
    result = evaluator.run(data_points)
    
    assert isinstance(result, EvaluatorResult)
    assert result.evaluator_name == "ToolUseEvaluator"
    assert result.agent_name == "test_agent"
    
    # Should have metrics for both tools
    assert len(result.metrics) == 4  # 2 tools * 2 metrics
    
    # Verify search tool has 50% failure rate
    search_failure = next(
        r for r in result.results if r.metric_name == "(search)_failure_rate"
    )
    assert search_failure.value == 0.5
    
    # Verify calculator has 0% failure rate
    calc_failure = next(
        r for r in result.results if r.metric_name == "(calculator)_failure_rate"
    )
    assert calc_failure.value == 0.0


def test_workflow_with_no_tool_invocations():
    """Test workflow when data points have no tool invocations."""
    evaluator = ToolUseEvaluator()
    
    data_point = AgentDataPoint(
        agent_name="test_agent",
        agent_input={"query": "test"},
        agent_output="result",
        agent_internals={"other_data": "some value"}
    )
    
    result = evaluator.run([data_point])
    
    assert isinstance(result, EvaluatorResult)
    assert len(result.metrics) == 0
    assert len(result.results) == 0


# ================= Edge Cases =================


def test_run_with_mixed_internals():
    """Test run with some data points having internals and some not."""
    evaluator = ToolUseEvaluator()
    
    data_points = [
        AgentDataPoint(
            agent_name="test_agent",
            agent_input={"query": "test1"},
            agent_output="result1",
            agent_internals={
                "tool_invocations": [
                    {"name": "tool", "result": "Success"}
                ]
            }
        ),
        AgentDataPoint(
            agent_name="test_agent",
            agent_input={"query": "test2"},
            agent_output="result2",
            agent_internals=None
        ),
        AgentDataPoint(
            agent_name="test_agent",
            agent_input={"query": "test3"},
            agent_output="result3",
            agent_internals={
                "tool_invocations": [
                    {"name": "tool", "result": "Success"}
                ]
            }
        )
    ]
    
    result = evaluator.run(data_points)
    
    # Should process the two valid data points
    usage_count = next(
        r for r in result.results if "usage_count" in r.metric_name
    )
    assert usage_count.value == 2


def test_tool_with_zero_invocations():
    """Test behavior when tool invocations list is present but empty."""
    evaluator = ToolUseEvaluator()
    
    data_point = AgentDataPoint(
        agent_name="test_agent",
        agent_input={"query": "test"},
        agent_output="result",
        agent_internals={"tool_invocations": []}
    )
    
    result = evaluator.run([data_point])
    
    assert len(result.metrics) == 0
    assert len(result.results) == 0


def test_same_tool_different_data_points():
    """Test that tool stats are correctly aggregated across data points."""
    evaluator = ToolUseEvaluator()
    
    data_points = [
        AgentDataPoint(
            agent_name="test_agent",
            agent_input={"query": f"test{i}"},
            agent_output=f"result{i}",
            agent_internals={
                "tool_invocations": [
                    {"name": "common_tool", "result": "Success"}
                ]
            }
        )
        for i in range(5)
    ]
    
    result = evaluator.run(data_points)
    
    usage_count = next(
        r for r in result.results if "usage_count" in r.metric_name
    )
    
    assert usage_count.value == 5


def test_metric_identifiers_are_valid_uuids():
    """Test that all metrics have valid UUID identifiers."""
    evaluator = ToolUseEvaluator()
    
    data_point = AgentDataPoint(
        agent_name="test_agent",
        agent_input={"query": "test"},
        agent_output="result",
        agent_internals={
            "tool_invocations": [
                {"name": "tool", "result": "Success"}
            ]
        }
    )
    
    result = evaluator.run([data_point])
    
    for metric in result.metrics:
        # Should be able to create UUID from identifier
        uuid_obj = UUID(metric.identifier)
        assert isinstance(uuid_obj, UUID)


def test_multiple_evaluator_instances_have_unique_ids():
    """Test that different evaluator instances have unique IDs."""
    evaluator1 = ToolUseEvaluator()
    evaluator2 = ToolUseEvaluator()
    
    assert evaluator1.id != evaluator2.id
