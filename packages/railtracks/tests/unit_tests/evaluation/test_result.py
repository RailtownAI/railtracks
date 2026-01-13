import pytest
from datetime import datetime
from uuid import UUID, uuid4

from railtracks.evaluation.result import (
    AgentRun,
    MetricResult,
    AggregateCategoricalResult,
    EvaluatorResult,
    EvaluationResult,
)
from railtracks.evaluation.evaluators.metrics import Categorical


# ================= AgentRun Tests =================


def test_agent_run_creation():
    """Test AgentRun creation with UUID objects and strings."""
    # Test with UUID objects
    session_id = uuid4()
    run_id = uuid4()
    agent_run = AgentRun(session_id=session_id, run_id=run_id)
    assert agent_run.session_id == session_id
    assert agent_run.run_id == run_id
    
    # Test with UUID strings
    session_str = "12345678-1234-5678-1234-567812345678"
    run_str = "87654321-4321-8765-4321-876543218765"
    agent_run = AgentRun(session_id=session_str, run_id=run_str)
    assert isinstance(agent_run.session_id, UUID)
    assert isinstance(agent_run.run_id, UUID)


# ================= MetricResult Tests =================


def test_metric_result_with_various_value_types():
    """Test MetricResult with different value types."""
    # String value
    result = MetricResult(metric_name="Sentiment", metric_id=uuid4(), value="Positive")
    assert result.value == "Positive" and isinstance(result.metric_id, UUID)
    
    # Float value
    result = MetricResult(metric_name="Accuracy", metric_id=uuid4(), value=0.95)
    assert result.value == 0.95 and isinstance(result.value, float)
    
    # Int value
    result = MetricResult(metric_name="Count", metric_id=uuid4(), value=42)
    assert result.value == 42 and isinstance(result.value, int)


# ================= AggregateCategoricalResult Tests =================


def test_aggregate_categorical_result_basic_creation(sample_categorical_metric):
    """Test AggregateCategoricalResult basic creation."""
    result = AggregateCategoricalResult(
        metric=sample_categorical_metric,
        labels=["Positive", "Negative", "Positive"]
    )
    
    assert result.metric == sample_categorical_metric
    assert result.labels == ["Positive", "Negative", "Positive"]
    assert result.counts == {"Positive": 2, "Negative": 1}


def test_aggregate_categorical_result_most_common_label(sample_categorical_metric):
    """Test most_common_label is computed correctly."""
    result = AggregateCategoricalResult(
        metric=sample_categorical_metric,
        labels=["Positive", "Negative", "Positive", "Neutral", "Positive"]
    )
    
    assert result.most_common_label == "Positive"
    assert result.counts["Positive"] == 3


def test_aggregate_categorical_result_least_common_label(sample_categorical_metric):
    """Test least_common_label is computed correctly."""
    result = AggregateCategoricalResult(
        metric=sample_categorical_metric,
        labels=["Positive", "Positive", "Negative"]
    )
    
    assert result.least_common_label == "Negative"
    assert result.counts["Negative"] == 1


def test_aggregate_categorical_result_edge_cases(sample_categorical_metric):
    """Test edge cases: single label, all same, equal counts."""
    # Single label
    result = AggregateCategoricalResult(metric=sample_categorical_metric, labels=["Positive"])
    assert result.most_common_label == result.least_common_label == "Positive"
    assert result.counts == {"Positive": 1}
    
    # All same labels
    result = AggregateCategoricalResult(metric=sample_categorical_metric, labels=["Neutral"] * 3)
    assert result.most_common_label == result.least_common_label == "Neutral"
    
    # Equal counts
    result = AggregateCategoricalResult(metric=sample_categorical_metric, labels=["Positive", "Negative"])
    assert result.most_common_label in ["Positive", "Negative"]


def test_aggregate_categorical_result_validation():
    """Test empty labels and invalid label validation."""
    metric = Categorical(name="Test", categories=["Valid1", "Valid2"])
    
    # Empty labels
    result = AggregateCategoricalResult(metric=metric, labels=[])
    assert result.counts == {} and result.most_common_label is None
    
    # Invalid labels raise exception
    with pytest.raises(Exception, match="Unknown label"):
        AggregateCategoricalResult(metric=metric, labels=["Valid1", "InvalidLabel"])
    
    # Case-sensitive validation
    metric2 = Categorical(name="Test", categories=["Positive", "Negative"])
    with pytest.raises(Exception, match="Unknown label"):
        AggregateCategoricalResult(metric=metric2, labels=["positive"])





# ================= EvaluatorResult Tests =================


def test_evaluator_result_creation_and_types(sample_categorical_metric, sample_numerical_metric):
    """Test EvaluatorResult creation with various result types."""
    evaluator_id = uuid4()
    metric_result = MetricResult(metric_name="test", metric_id=uuid4(), value="test_value")
    
    # Basic creation
    result = EvaluatorResult(
        evaluator_name="TestEvaluator",
        agent_name="test_agent",
        evaluator_id=evaluator_id,
        metrics=[sample_categorical_metric],
        results=[metric_result]
    )
    assert result.evaluator_name == "TestEvaluator" and len(result.metrics) == 1
    
    # Multiple metrics
    result = EvaluatorResult(
        evaluator_name="TestEvaluator",
        agent_name="test_agent",
        evaluator_id=uuid4(),
        metrics=[sample_categorical_metric, sample_numerical_metric],
        results=[]
    )
    assert len(result.metrics) == 2
    
    # Tuple and aggregate results
    aggregate = AggregateCategoricalResult(metric=sample_categorical_metric, labels=["Positive"])
    tuple_result = (uuid4(), metric_result)
    result = EvaluatorResult(
        evaluator_name="TestEvaluator",
        agent_name="test_agent",
        evaluator_id=uuid4(),
        metrics=[sample_categorical_metric],
        results=[tuple_result, aggregate, metric_result]
    )
    assert len(result.results) == 3


# ================= EvaluationResult Tests =================


def test_evaluation_result_comprehensive(sample_categorical_metric):
    """Test EvaluationResult creation with various configurations."""
    evaluation_id = uuid4()
    run_id1, run_id2 = uuid4(), uuid4()
    dp_id1, dp_id2 = uuid4(), uuid4()
    
    evaluator_result = EvaluatorResult(
        evaluator_name="TestEvaluator",
        agent_name="test_agent",
        evaluator_id=uuid4(),
        metrics=[],
        results=[]
    )
    
    # Basic creation with IDs and data points
    result = EvaluationResult(
        evaluation_id=evaluation_id,
        evaluation_name="Test Evaluation",
        agent_name="test_agent",
        created_at=datetime.now(),
        agent_run_ids=[run_id1, run_id2],
        data_points=[dp_id1, dp_id2],
        results=[evaluator_result],
        metrics=[sample_categorical_metric]
    )
    
    assert result.evaluation_id == evaluation_id
    assert len(result.agent_run_ids) == 2
    assert len(result.data_points) == 2
    assert len(result.results) == 1
    
    # JSON serialization
    json_data = result.model_dump(mode="json")
    assert "evaluation_id" in json_data and "created_at" in json_data


# ================= Integration Tests =================


def test_full_result_structure(sample_categorical_metric):
    """Test a complete result structure."""
    # Create metric result
    metric_result = MetricResult(
        metric_name="Sentiment",
        metric_id=UUID(sample_categorical_metric.identifier),
        value="Positive"
    )
    
    # Create aggregate result
    aggregate = AggregateCategoricalResult(
        metric=sample_categorical_metric,
        labels=["Positive", "Positive", "Negative"]
    )
    
    # Create evaluator result
    evaluator_result = EvaluatorResult(
        evaluator_name="JudgeEvaluator",
        agent_name="test_agent",
        evaluator_id=uuid4(),
        metrics=[sample_categorical_metric],
        results=[metric_result, aggregate]
    )
    
    # Create evaluation result
    evaluation_result = EvaluationResult(
        evaluation_id=uuid4(),
        evaluation_name="Test Evaluation",
        agent_name="test_agent",
        created_at=datetime.now(),
        results=[evaluator_result],
        metrics=[sample_categorical_metric]
    )
    
    # Verify structure
    assert len(evaluation_result.results) == 1
    assert len(evaluation_result.results[0].results) == 2
    assert evaluation_result.results[0].results[1].most_common_label == "Positive"
