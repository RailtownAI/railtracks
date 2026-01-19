import pytest
from datetime import datetime
from uuid import UUID, uuid4

from railtracks.evaluation.result import (
    MetricResult,
    AggregateCategoricalResult,
    AggregateNumericalResult,
    EvaluatorResult,
    EvaluationResult,
)
from railtracks.evaluation.evaluators.metrics import Categorical, Numerical


# ================= MetricResult Tests =================


def test_metric_result_with_various_value_types():
    """Test MetricResult with different value types."""
    # String value
    result = MetricResult(metric_name="Sentiment", metric_id=str(uuid4()), value="Positive")
    assert result.value == "Positive" and isinstance(result.metric_id, str)
    
    # Float value
    result = MetricResult(metric_name="Accuracy", metric_id=str(uuid4()), value=0.95)
    assert result.value == 0.95 and isinstance(result.value, float)
    
    # Int value
    result = MetricResult(metric_name="Count", metric_id=str(uuid4()), value=42)
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


# ================= AggregateNumericalResult Tests =================


def test_aggregate_numerical_result_basic_creation(sample_numerical_metric):
    """Test AggregateNumericalResult basic creation."""
    result = AggregateNumericalResult(
        metric=sample_numerical_metric,
        values=[0.5, 0.7, 0.9]
    )
    
    assert result.metric == sample_numerical_metric
    assert result.values == [0.5, 0.7, 0.9]
    assert result.mean is not None
    assert result.minimum is not None
    assert result.maximum is not None


def test_aggregate_numerical_result_statistics(sample_numerical_metric):
    """Test statistical calculations are correct."""
    result = AggregateNumericalResult(
        metric=sample_numerical_metric,
        values=[1.0, 2.0, 3.0, 4.0, 5.0]
    )
    
    # Check mean
    assert result.mean == 3.0
    
    # Check min/max
    assert result.minimum == 1.0
    assert result.maximum == 5.0
    
    # Check median
    assert result.median == 3.0
    
    # Check mode (all values unique, so mode is any of them)
    assert result.mode in [1.0, 2.0, 3.0, 4.0, 5.0]


def test_aggregate_numerical_result_median_even_count(sample_numerical_metric):
    """Test median calculation with even number of values."""
    result = AggregateNumericalResult(
        metric=sample_numerical_metric,
        values=[1.0, 2.0, 3.0, 4.0]
    )
    
    # Median of even count should be average of middle two
    assert result.median == 2.5


def test_aggregate_numerical_result_median_odd_count(sample_numerical_metric):
    """Test median calculation with odd number of values."""
    result = AggregateNumericalResult(
        metric=sample_numerical_metric,
        values=[1.0, 2.0, 3.0]
    )
    
    # Median of odd count should be middle value
    assert result.median == 2.0


def test_aggregate_numerical_result_mode_calculation(sample_numerical_metric):
    """Test mode calculation with repeated values."""
    result = AggregateNumericalResult(
        metric=sample_numerical_metric,
        values=[0.5, 0.7, 0.5, 0.9, 0.5]
    )
    
    # Mode should be most common value
    assert result.mode == 0.5


def test_aggregate_numerical_result_std_calculation(sample_numerical_metric):
    """Test standard deviation calculation."""
    result = AggregateNumericalResult(
        metric=sample_numerical_metric,
        values=[2.0, 4.0, 4.0, 4.0, 5.0, 5.0, 7.0, 9.0]
    )
    
    # Check std is calculated (should be approximately 2.0)
    assert result.std is not None
    assert isinstance(result.std, float)
    assert result.std > 0


def test_aggregate_numerical_result_single_value(sample_numerical_metric):
    """Test with single value."""
    result = AggregateNumericalResult(
        metric=sample_numerical_metric,
        values=[0.75]
    )
    
    assert result.mean == 0.75
    assert result.minimum == 0.75
    assert result.maximum == 0.75
    assert result.median == 0.75
    assert result.std == 0.0
    assert result.mode == 0.75


def test_aggregate_numerical_result_empty_values(sample_numerical_metric):
    """Test with empty values list."""
    result = AggregateNumericalResult(
        metric=sample_numerical_metric,
        values=[]
    )
    
    assert result.values == []
    assert result.mean is None
    assert result.minimum is None
    assert result.maximum is None
    assert result.median is None
    assert result.std is None
    assert result.mode is None


def test_aggregate_numerical_result_integer_values(sample_numerical_metric):
    """Test with integer values."""
    result = AggregateNumericalResult(
        metric=sample_numerical_metric,
        values=[1, 2, 3, 4, 5]
    )
    
    assert result.mean == 3.0
    assert result.minimum == 1
    assert result.maximum == 5
    assert result.median == 3


def test_aggregate_numerical_result_mixed_types(sample_numerical_metric):
    """Test with mixed int and float values."""
    result = AggregateNumericalResult(
        metric=sample_numerical_metric,
        values=[1, 2.5, 3, 4.5, 5]
    )
    
    assert result.mean == 3.2
    assert result.minimum == 1
    assert result.maximum == 5


def test_aggregate_numerical_result_negative_values(sample_numerical_metric):
    """Test with negative values."""
    result = AggregateNumericalResult(
        metric=sample_numerical_metric,
        values=[-5.0, -2.0, 0.0, 2.0, 5.0]
    )
    
    assert result.mean == 0.0
    assert result.minimum == -5.0
    assert result.maximum == 5.0
    assert result.median == 0.0


# ================= EvaluatorResult Tests =================


def test_evaluator_result_creation_and_types(sample_categorical_metric, sample_numerical_metric):
    """Test EvaluatorResult creation with various result types."""
    evaluator_id = uuid4()
    metric_result = MetricResult(metric_name="test", metric_id=str(uuid4()), value="test_value")
    
    # Basic creation
    result = EvaluatorResult(
        evaluator_name="TestEvaluator",
        evaluator_id=evaluator_id,
        metrics=[sample_categorical_metric],
        results=[metric_result]
    )
    assert result.evaluator_name == "TestEvaluator" and len(result.metrics) == 1
    
    # Multiple metrics
    result = EvaluatorResult(
        evaluator_name="TestEvaluator",
        evaluator_id=uuid4(),
        metrics=[sample_categorical_metric, sample_numerical_metric],
        results=[]
    )
    assert len(result.metrics) == 2
    
    # Tuple and aggregate results
    categorical_aggregate = AggregateCategoricalResult(metric=sample_categorical_metric, labels=["Positive"])
    numerical_aggregate = AggregateNumericalResult(metric=sample_numerical_metric, values=[0.8, 0.9])
    data_point_id = uuid4()
    tuple_result = (data_point_id, metric_result)
    result = EvaluatorResult(
        evaluator_name="TestEvaluator",
        evaluator_id=uuid4(),
        agent_data_ids={data_point_id},
        metrics=[sample_categorical_metric, sample_numerical_metric],
        results=[tuple_result, categorical_aggregate, numerical_aggregate, metric_result]
    )
    assert len(result.results) == 4


# ================= EvaluationResult Tests =================


def test_evaluation_result_comprehensive(sample_categorical_metric):
    """Test EvaluationResult creation with various configurations."""
    evaluation_id = uuid4()
    run_id1, run_id2 = uuid4(), uuid4()
    dp_id1, dp_id2 = uuid4(), uuid4()
    
    evaluator_result = EvaluatorResult(
        evaluator_name="TestEvaluator",
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


def test_full_result_structure(sample_categorical_metric, sample_numerical_metric):
    """Test a complete result structure."""
    # Create metric result
    metric_result = MetricResult(
        metric_name="Sentiment",
        metric_id=sample_categorical_metric.identifier,
        value="Positive"
    )
    
    # Create aggregate results
    categorical_aggregate = AggregateCategoricalResult(
        metric=sample_categorical_metric,
        labels=["Positive", "Positive", "Negative"]
    )
    
    numerical_aggregate = AggregateNumericalResult(
        metric=sample_numerical_metric,
        values=[0.85, 0.92, 0.78, 0.90]
    )
    
    # Create evaluator result
    evaluator_result = EvaluatorResult(
        evaluator_name="JudgeEvaluator",
        evaluator_id=uuid4(),
        metrics=[sample_categorical_metric, sample_numerical_metric],
        results=[metric_result, categorical_aggregate, numerical_aggregate]
    )
    
    # Create evaluation result
    evaluation_result = EvaluationResult(
        evaluation_id=uuid4(),
        evaluation_name="Test Evaluation",
        agent_name="test_agent",
        created_at=datetime.now(),
        results=[evaluator_result],
        metrics=[sample_categorical_metric, sample_numerical_metric]
    )
    
    # Verify structure
    assert len(evaluation_result.results) == 1
    assert len(evaluation_result.results[0].results) == 3
    assert evaluation_result.results[0].results[1].most_common_label == "Positive"
    assert evaluation_result.results[0].results[2].mean is not None
