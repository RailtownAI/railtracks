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
from railtracks.evaluation.evaluators.metrics import Categorical, Numerical


# ================= AgentRun Tests =================


def test_agent_run_creation():
    """Test AgentRun basic creation."""
    session_id = uuid4()
    run_id = uuid4()
    
    agent_run = AgentRun(session_id=session_id, run_id=run_id)
    
    assert agent_run.session_id == session_id
    assert agent_run.run_id == run_id


def test_agent_run_with_uuid_strings():
    """Test AgentRun accepts UUID strings."""
    session_id = "12345678-1234-5678-1234-567812345678"
    run_id = "87654321-4321-8765-4321-876543218765"
    
    agent_run = AgentRun(session_id=session_id, run_id=run_id)
    
    assert isinstance(agent_run.session_id, UUID)
    assert isinstance(agent_run.run_id, UUID)


# ================= MetricResult Tests =================


def test_metric_result_with_string_value():
    """Test MetricResult with string value."""
    result = MetricResult(
        metric_name="Sentiment",
        metric_id=uuid4(),
        value="Positive"
    )
    
    assert result.metric_name == "Sentiment"
    assert isinstance(result.metric_id, UUID)
    assert result.value == "Positive"


def test_metric_result_with_float_value():
    """Test MetricResult with float value."""
    result = MetricResult(
        metric_name="Accuracy",
        metric_id=uuid4(),
        value=0.95
    )
    
    assert result.value == 0.95
    assert isinstance(result.value, float)


def test_metric_result_with_int_value():
    """Test MetricResult with integer value."""
    result = MetricResult(
        metric_name="Count",
        metric_id=uuid4(),
        value=42
    )
    
    assert result.value == 42
    assert isinstance(result.value, int)


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


def test_aggregate_categorical_result_single_label(sample_categorical_metric):
    """Test with a single label."""
    result = AggregateCategoricalResult(
        metric=sample_categorical_metric,
        labels=["Positive"]
    )
    
    assert result.most_common_label == "Positive"
    assert result.least_common_label == "Positive"
    assert result.counts == {"Positive": 1}


def test_aggregate_categorical_result_all_same_labels(sample_categorical_metric):
    """Test with all labels being the same."""
    result = AggregateCategoricalResult(
        metric=sample_categorical_metric,
        labels=["Neutral", "Neutral", "Neutral"]
    )
    
    assert result.most_common_label == "Neutral"
    assert result.least_common_label == "Neutral"
    assert result.counts == {"Neutral": 3}


def test_aggregate_categorical_result_multiple_labels_equal_count(sample_categorical_metric):
    """Test behavior when multiple labels have equal counts."""
    result = AggregateCategoricalResult(
        metric=sample_categorical_metric,
        labels=["Positive", "Negative"]
    )
    
    # Should still set most and least common (will be one of them)
    assert result.most_common_label in ["Positive", "Negative"]
    assert result.least_common_label in ["Positive", "Negative"]
    assert result.counts == {"Positive": 1, "Negative": 1}


def test_aggregate_categorical_result_empty_labels():
    """Test with empty labels list."""
    metric = Categorical(name="Test", categories=["A", "B"])
    
    result = AggregateCategoricalResult(
        metric=metric,
        labels=[]
    )
    
    assert result.counts == {}
    assert result.most_common_label is None
    assert result.least_common_label is None


def test_aggregate_categorical_result_invalid_label_raises_exception():
    """Test that invalid label raises exception."""
    metric = Categorical(name="Test", categories=["Valid1", "Valid2"])
    
    with pytest.raises(Exception, match="Unknown label"):
        AggregateCategoricalResult(
            metric=metric,
            labels=["Valid1", "InvalidLabel"]
        )


def test_aggregate_categorical_result_all_invalid_labels_raises_exception():
    """Test that all invalid labels raises exception."""
    metric = Categorical(name="Test", categories=["Valid1", "Valid2"])
    
    with pytest.raises(Exception, match="Unknown label"):
        AggregateCategoricalResult(
            metric=metric,
            labels=["Invalid1", "Invalid2"]
        )


def test_aggregate_categorical_result_case_sensitive_labels():
    """Test that label validation is case-sensitive."""
    metric = Categorical(name="Test", categories=["Positive", "Negative"])
    
    with pytest.raises(Exception, match="Unknown label"):
        AggregateCategoricalResult(
            metric=metric,
            labels=["positive"]  # lowercase should not match
        )


def test_aggregate_categorical_result_counts_dict_structure(sample_categorical_metric):
    """Test counts dictionary has correct structure."""
    result = AggregateCategoricalResult(
        metric=sample_categorical_metric,
        labels=["Positive", "Positive", "Negative", "Neutral", "Positive"]
    )
    
    assert isinstance(result.counts, dict)
    assert all(isinstance(k, str) for k in result.counts.keys())
    assert all(isinstance(v, int) for v in result.counts.values())
    assert sum(result.counts.values()) == 5  # Total count


def test_aggregate_categorical_result_preserves_original_labels(sample_categorical_metric):
    """Test that original labels list is preserved."""
    original_labels = ["Positive", "Negative", "Positive"]
    
    result = AggregateCategoricalResult(
        metric=sample_categorical_metric,
        labels=original_labels
    )
    
    assert result.labels == original_labels


def test_aggregate_categorical_result_with_all_categories(sample_categorical_metric):
    """Test with all categories from metric present."""
    result = AggregateCategoricalResult(
        metric=sample_categorical_metric,
        labels=["Positive", "Negative", "Neutral", "Positive"]
    )
    
    assert len(result.counts) == 3
    assert "Positive" in result.counts
    assert "Negative" in result.counts
    assert "Neutral" in result.counts


# ================= EvaluatorResult Tests =================


def test_evaluator_result_creation(sample_categorical_metric):
    """Test EvaluatorResult basic creation."""
    evaluator_id = uuid4()
    metric_id = uuid4()
    
    metric_result = MetricResult(
        metric_name="test_metric",
        metric_id=metric_id,
        value="test_value"
    )
    
    result = EvaluatorResult(
        evaluator_name="TestEvaluator",
        agent_name="test_agent",
        evaluator_id=evaluator_id,
        metrics=[sample_categorical_metric],
        results=[metric_result]
    )
    
    assert result.evaluator_name == "TestEvaluator"
    assert result.agent_name == "test_agent"
    assert result.evaluator_id == evaluator_id
    assert len(result.metrics) == 1
    assert len(result.results) == 1


def test_evaluator_result_with_empty_results():
    """Test EvaluatorResult with empty results."""
    result = EvaluatorResult(
        evaluator_name="TestEvaluator",
        agent_name="test_agent",
        evaluator_id=uuid4(),
        metrics=[],
        results=[]
    )
    
    assert len(result.metrics) == 0
    assert len(result.results) == 0


def test_evaluator_result_with_multiple_metrics(sample_categorical_metric, sample_numerical_metric):
    """Test EvaluatorResult with multiple metrics."""
    result = EvaluatorResult(
        evaluator_name="TestEvaluator",
        agent_name="test_agent",
        evaluator_id=uuid4(),
        metrics=[sample_categorical_metric, sample_numerical_metric],
        results=[]
    )
    
    assert len(result.metrics) == 2


def test_evaluator_result_with_tuple_results():
    """Test EvaluatorResult with tuple results."""
    data_point_id = uuid4()
    metric_result = MetricResult(
        metric_name="test",
        metric_id=uuid4(),
        value=1.0
    )
    
    result = EvaluatorResult(
        evaluator_name="TestEvaluator",
        agent_name="test_agent",
        evaluator_id=uuid4(),
        metrics=[],
        results=[(data_point_id, metric_result)]
    )
    
    assert len(result.results) == 1
    assert isinstance(result.results[0], tuple)


def test_evaluator_result_with_aggregate_results(sample_categorical_metric):
    """Test EvaluatorResult with AggregateCategoricalResult."""
    aggregate = AggregateCategoricalResult(
        metric=sample_categorical_metric,
        labels=["Positive", "Negative"]
    )
    
    result = EvaluatorResult(
        evaluator_name="TestEvaluator",
        agent_name="test_agent",
        evaluator_id=uuid4(),
        metrics=[sample_categorical_metric],
        results=[aggregate]
    )
    
    assert len(result.results) == 1
    assert isinstance(result.results[0], AggregateCategoricalResult)


def test_evaluator_result_with_mixed_result_types(sample_categorical_metric):
    """Test EvaluatorResult with mixed result types."""
    metric_result = MetricResult(
        metric_name="test",
        metric_id=uuid4(),
        value=0.5
    )
    
    aggregate = AggregateCategoricalResult(
        metric=sample_categorical_metric,
        labels=["Positive"]
    )
    
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


def test_evaluation_result_creation():
    """Test EvaluationResult basic creation."""
    evaluation_id = uuid4()
    evaluator_id = uuid4()
    
    evaluator_result = EvaluatorResult(
        evaluator_name="TestEvaluator",
        agent_name="test_agent",
        evaluator_id=evaluator_id,
        metrics=[],
        results=[]
    )
    
    result = EvaluationResult(
        evaluation_id=evaluation_id,
        evaluation_name="Test Evaluation",
        agent_name="test_agent",
        created_at=datetime.now(),
        results=[evaluator_result],
        metrics=[]
    )
    
    assert result.evaluation_id == evaluation_id
    assert result.evaluation_name == "Test Evaluation"
    assert result.agent_name == "test_agent"
    assert isinstance(result.created_at, datetime)
    assert len(result.results) == 1


def test_evaluation_result_with_default_lists():
    """Test EvaluationResult with default empty lists."""
    result = EvaluationResult(
        evaluation_id=uuid4(),
        evaluation_name="Test",
        agent_name="test_agent",
        created_at=datetime.now(),
        results=[],
        metrics=[]
    )
    
    assert result.agent_run_ids == []
    assert result.data_points == []


def test_evaluation_result_with_agent_run_ids():
    """Test EvaluationResult with agent run IDs."""
    run_id1 = uuid4()
    run_id2 = uuid4()
    
    result = EvaluationResult(
        evaluation_id=uuid4(),
        evaluation_name="Test",
        agent_name="test_agent",
        created_at=datetime.now(),
        agent_run_ids=[run_id1, run_id2],
        results=[],
        metrics=[]
    )
    
    assert len(result.agent_run_ids) == 2
    assert run_id1 in result.agent_run_ids
    assert run_id2 in result.agent_run_ids


def test_evaluation_result_with_data_points():
    """Test EvaluationResult with data point UUIDs."""
    dp_id1 = uuid4()
    dp_id2 = uuid4()
    
    result = EvaluationResult(
        evaluation_id=uuid4(),
        evaluation_name="Test",
        agent_name="test_agent",
        created_at=datetime.now(),
        data_points=[dp_id1, dp_id2],
        results=[],
        metrics=[]
    )
    
    assert len(result.data_points) == 2
    assert dp_id1 in result.data_points
    assert dp_id2 in result.data_points


def test_evaluation_result_with_multiple_evaluator_results(sample_categorical_metric):
    """Test EvaluationResult with multiple evaluator results."""
    evaluator_result1 = EvaluatorResult(
        evaluator_name="Evaluator1",
        agent_name="test_agent",
        evaluator_id=uuid4(),
        metrics=[sample_categorical_metric],
        results=[]
    )
    
    evaluator_result2 = EvaluatorResult(
        evaluator_name="Evaluator2",
        agent_name="test_agent",
        evaluator_id=uuid4(),
        metrics=[],
        results=[]
    )
    
    result = EvaluationResult(
        evaluation_id=uuid4(),
        evaluation_name="Test",
        agent_name="test_agent",
        created_at=datetime.now(),
        results=[evaluator_result1, evaluator_result2],
        metrics=[sample_categorical_metric]
    )
    
    assert len(result.results) == 2


def test_evaluation_result_json_serialization():
    """Test EvaluationResult can be serialized to JSON."""
    result = EvaluationResult(
        evaluation_id=uuid4(),
        evaluation_name="Test",
        agent_name="test_agent",
        created_at=datetime.now(),
        results=[],
        metrics=[]
    )
    
    json_data = result.model_dump(mode="json")
    
    assert "evaluation_id" in json_data
    assert "evaluation_name" in json_data
    assert "agent_name" in json_data
    assert "created_at" in json_data


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
