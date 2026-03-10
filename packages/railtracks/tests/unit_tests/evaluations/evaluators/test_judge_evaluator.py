from uuid import UUID

from railtracks.evaluation.evaluators.judge_evaluator import (
    JudgeEvaluator,
    JudgeResponseSchema,
)
from railtracks.evaluation.evaluators.metrics import Numerical, Categorical
from railtracks.evaluation.result import EvaluatorResult
from railtracks.utils.point import AgentDataPoint


# ================= Schema Validation Tests =================


def test_judge_response_schema_with_string_value():
    """Test JudgeResponseSchema with string metric value."""
    response = JudgeResponseSchema(
        metric_value="Positive",
        reasoning="Test reasoning"
    )
    
    assert isinstance(response.metric_value, str)
    assert response.metric_value == "Positive"
    assert response.reasoning == "Test reasoning"


def test_judge_response_schema_with_numeric_values():
    """Test JudgeResponseSchema with numeric values."""
    response_float = JudgeResponseSchema(
        metric_value=0.95,
        reasoning="Float value"
    )
    response_int = JudgeResponseSchema(
        metric_value=42,
        reasoning="Integer value"
    )
    
    assert response_float.metric_value == 0.95
    assert response_int.metric_value == 42


def test_judge_response_schema_with_null_reasoning():
    """Test JudgeResponseSchema handles null reasoning."""
    response = JudgeResponseSchema(
        metric_value="Positive",
        reasoning=None
    )
    
    assert response.metric_value == "Positive"
    assert response.reasoning is None


def test_judge_response_schema_json_serialization():
    """Test JudgeResponseSchema can be serialized to JSON."""
    response = JudgeResponseSchema(
        metric_value="Positive",
        reasoning="Detailed reasoning here"
    )
    
    json_data = response.model_dump(mode="json")
    
    assert "metric_value" in json_data
    assert "reasoning" in json_data
    assert json_data["metric_value"] == "Positive"


def test_judge_response_schema_from_dict():
    """Test JudgeResponseSchema can be created from dictionary."""
    data = {
        "metric_value": "Negative",
        "reasoning": "Analysis complete"
    }
    
    response = JudgeResponseSchema.model_validate(data)
    
    assert response.metric_value == "Negative"
    assert response.reasoning == "Analysis complete"


# ================= Initialization Tests =================


def test_judge_evaluator_initialization_with_defaults(sample_categorical_metric, mock_llm):
    """Test JudgeEvaluator initialization with default parameters."""
    llm = mock_llm()
    evaluator = JudgeEvaluator(
        llm=llm,
        metrics=[sample_categorical_metric],
    )
    
    assert evaluator._llm == llm
    assert evaluator._reasoning is True
    assert len(evaluator._metrics) == 1
    assert sample_categorical_metric.identifier in evaluator._metrics
    assert evaluator._metrics[sample_categorical_metric.identifier] == sample_categorical_metric
    assert evaluator.name == "JudgeEvaluator"
    assert isinstance(evaluator.id, UUID)


def test_judge_evaluator_initialization_with_custom_params(sample_categorical_metric, mock_llm):
    """Test JudgeEvaluator initialization with custom parameters."""
    llm = mock_llm()
    custom_prompt = "You are a strict evaluator."
    
    evaluator = JudgeEvaluator(
        llm=llm,
        metrics=[sample_categorical_metric],
        system_prompt=custom_prompt,
        reasoning=False,
    )
    
    assert evaluator._llm == llm
    assert evaluator._reasoning is False


def test_judge_evaluator_initialization_with_multiple_metrics(multiple_metrics, mock_llm):
    """Test JudgeEvaluator initialization with multiple metrics."""
    llm = mock_llm()
    evaluator = JudgeEvaluator(
        llm=llm,
        metrics=multiple_metrics,
    )
    
    assert len(evaluator._metrics) == 3
    for metric in multiple_metrics:
        assert metric.identifier in evaluator._metrics
        assert evaluator._metrics[metric.identifier] == metric


def test_judge_evaluator_creates_metrics_dict(sample_categorical_metric, mock_llm):
    """Test that JudgeEvaluator creates a metrics dictionary indexed by identifier."""
    llm = mock_llm()
    evaluator = JudgeEvaluator(
        llm=llm,
        metrics=[sample_categorical_metric],
    )
    
    assert sample_categorical_metric.identifier in evaluator._metrics
    assert evaluator._metrics[sample_categorical_metric.identifier] == sample_categorical_metric


# ================= Prompt Generation Tests =================


def test_generate_system_prompt_with_metric(sample_categorical_metric, mock_llm):
    """Test _generate_system_prompt generates prompt for a specific metric."""
    llm = mock_llm()
    evaluator = JudgeEvaluator(
        llm=llm,
        metrics=[sample_categorical_metric],
    )
    
    system_prompt = evaluator._generate_system_prompt(sample_categorical_metric)
    
    assert isinstance(system_prompt, str)
    assert len(system_prompt) > 0
    assert str(sample_categorical_metric) in system_prompt or sample_categorical_metric.name in system_prompt


def test_generate_system_prompt_includes_reasoning(sample_categorical_metric, mock_llm):
    """Test system prompt includes reasoning when enabled."""
    llm = mock_llm()
    
    evaluator_with_reasoning = JudgeEvaluator(
        llm=llm,
        metrics=[sample_categorical_metric],
        reasoning=True,
    )
    
    evaluator_without_reasoning = JudgeEvaluator(
        llm=llm,
        metrics=[sample_categorical_metric],
        reasoning=False,
    )
    
    prompt_with = evaluator_with_reasoning._generate_system_prompt(sample_categorical_metric)
    prompt_without = evaluator_without_reasoning._generate_system_prompt(sample_categorical_metric)
    
    assert "reasoning" in prompt_with.lower()
    assert "reasoning" not in prompt_without.lower()


def test_generate_user_prompt_formats_data_point(sample_categorical_metric, sample_data_points, mock_llm):
    """Test _generate_user_prompt correctly formats a data point."""
    llm = mock_llm()
    evaluator = JudgeEvaluator(
        llm=llm,
        metrics=[sample_categorical_metric],
    )
    
    data_point = sample_data_points[0]
    user_prompt = evaluator._generate_user_prompt(data_point)
    
    assert isinstance(user_prompt, str)
    assert str(data_point.agent_input) in user_prompt or "What is AI?" in user_prompt
    assert str(data_point.agent_output) in user_prompt or "Artificial Intelligence" in user_prompt


def test_generate_user_prompt_handles_none_internals(sample_categorical_metric, mock_llm):
    """Test _generate_user_prompt handles None agent_internals."""
    llm = mock_llm()
    evaluator = JudgeEvaluator(
        llm=llm,
        metrics=[sample_categorical_metric],
    )
    
    data_point = AgentDataPoint(
        agent_name="test",
        agent_input={"query": "test"},
        agent_output="output",
        agent_internals=None,
    )
    
    user_prompt = evaluator._generate_user_prompt(data_point)
    
    assert isinstance(user_prompt, str)
    assert len(user_prompt) > 0


def test_generate_user_prompt_includes_internals(sample_categorical_metric, mock_llm):
    """Test _generate_user_prompt includes agent internals when present."""
    llm = mock_llm()
    evaluator = JudgeEvaluator(
        llm=llm,
        metrics=[sample_categorical_metric],
    )
    
    data_point = AgentDataPoint(
        agent_name="test",
        agent_input={"query": "test"},
        agent_output="output",
        agent_internals={"steps": 5, "tokens": 100},
    )
    
    user_prompt = evaluator._generate_user_prompt(data_point)
    
    assert isinstance(user_prompt, str)
    assert "steps" in user_prompt or str(data_point.agent_internals) in user_prompt


# ================= Aggregate Metrics Tests =================


def test_aggregate_metrics_with_categorical(sample_categorical_metric, mock_llm):
    """Test _aggregate_metrics creates aggregate for categorical metrics."""
    llm = mock_llm()
    evaluator = JudgeEvaluator(
        llm=llm,
        metrics=[sample_categorical_metric],
    )
    
    # Manually populate results to test aggregation
    from railtracks.evaluation.result import MetricResult
    evaluator.results[sample_categorical_metric] = [
        ("id1", MetricResult(
            metric_name=sample_categorical_metric.name,
            metric_id=sample_categorical_metric.identifier,
            value="Positive"
        )),
        ("id2", MetricResult(
            metric_name=sample_categorical_metric.name,
            metric_id=sample_categorical_metric.identifier,
            value="Negative"
        )),
    ]
    
    aggregates = evaluator._aggregate_metrics()
    
    assert len(aggregates) == 1
    assert aggregates[0].metric == sample_categorical_metric


def test_aggregate_metrics_with_numerical(sample_numerical_metric, mock_llm):
    """Test _aggregate_metrics creates aggregate for numerical metrics."""
    llm = mock_llm()
    evaluator = JudgeEvaluator(
        llm=llm,
        metrics=[sample_numerical_metric],
    )
    
    # Manually populate results to test aggregation
    from railtracks.evaluation.result import MetricResult
    evaluator.results[sample_numerical_metric] = [
        ("id1", MetricResult(
            metric_name=sample_numerical_metric.name,
            metric_id=sample_numerical_metric.identifier,
            value=0.8
        )),
        ("id2", MetricResult(
            metric_name=sample_numerical_metric.name,
            metric_id=sample_numerical_metric.identifier,
            value=0.9
        )),
    ]
    
    aggregates = evaluator._aggregate_metrics()
    
    assert len(aggregates) == 1
    assert aggregates[0].metric == sample_numerical_metric


def test_aggregate_metrics_with_mixed_metrics(multiple_metrics, mock_llm):
    """Test _aggregate_metrics with mixed metric types."""
    llm = mock_llm()
    evaluator = JudgeEvaluator(
        llm=llm,
        metrics=multiple_metrics,
    )
    
    # Manually populate results for each metric with valid values
    from railtracks.evaluation.result import MetricResult
    for metric in multiple_metrics:
        if isinstance(metric, Categorical):
            # Use valid category value for each metric
            if metric.name == "Sentiment":
                value = "Positive"  # Valid for Sentiment metric
            elif metric.name == "Helpfulness":
                value = "Helpful"  # Valid for Helpfulness metric
            else:
                value = metric.categories[0] if metric.categories else "Unknown"
            
            evaluator.results[metric] = [
                ("id1", MetricResult(
                    metric_name=metric.name,
                    metric_id=metric.identifier,
                    value=value
                )),
            ]
        elif isinstance(metric, Numerical):
            evaluator.results[metric] = [
                ("id1", MetricResult(
                    metric_name=metric.name,
                    metric_id=metric.identifier,
                    value=0.9
                )),
            ]
    
    aggregates = evaluator._aggregate_metrics()
    
    # Should aggregate all metrics (both categorical and numerical)
    assert len(aggregates) == 3


# ================= Run Method Tests =================
# Note: Actual .run() tests require real LLM integration and belong in integration tests


# ================= Repr Tests =================


def test_repr_includes_all_parameters(sample_categorical_metric, mock_llm):
    """Test __repr__ includes key initialization parameters."""
    llm = mock_llm()
    evaluator = JudgeEvaluator(
        llm=llm,
        metrics=[sample_categorical_metric],
        reasoning=False,
    )
    
    repr_str = repr(evaluator)
    
    assert "JudgeEvaluator" in repr_str
    assert "llm" in repr_str
    assert "metrics" in repr_str
    assert "reasoning" in repr_str


def test_repr_is_consistent(sample_categorical_metric, mock_llm):
    """Test __repr__ returns consistent results."""
    llm = mock_llm()
    evaluator = JudgeEvaluator(
        llm=llm,
        metrics=[sample_categorical_metric],
    )
    
    repr1 = repr(evaluator)
    repr2 = repr(evaluator)
    
    assert repr1 == repr2


# ================= YAML Loading Tests =================


def test_load_yaml_loads_template(sample_categorical_metric, mock_llm):
    """Test that YAML template is loaded correctly."""
    llm = mock_llm()
    evaluator = JudgeEvaluator(
        llm=llm,
        metrics=[sample_categorical_metric],
    )
    
    assert evaluator._template is not None
    assert "system_prompt" in evaluator._template
    assert "user" in evaluator._template
    assert "metric" in evaluator._template
    assert "reasoning" in evaluator._template


def test_yaml_template_has_required_keys(sample_categorical_metric, mock_llm):
    """Test YAML template contains all required keys."""
    llm = mock_llm()
    evaluator = JudgeEvaluator(
        llm=llm,
        metrics=[sample_categorical_metric],
    )
    
    required_keys = ["system_prompt", "user", "metric", "reasoning"]
    for key in required_keys:
        assert key in evaluator._template


# ================= Edge Cases =================


def test_evaluator_with_empty_metrics_list(mock_llm):
    """Test evaluator with empty metrics list."""
    llm = mock_llm()
    evaluator = JudgeEvaluator(
        llm=llm,
        metrics=[],
    )
    
    assert len(evaluator._metrics) == 0


def test_evaluator_result_structure(sample_categorical_metric, mock_llm):
    """Test that evaluator initializes results structure correctly."""
    llm = mock_llm()
    evaluator = JudgeEvaluator(
        llm=llm,
        metrics=[sample_categorical_metric],
    )
    
    assert hasattr(evaluator, 'results')
    assert isinstance(evaluator.results, dict)
    assert hasattr(evaluator, 'agent_data_ids')
    assert isinstance(evaluator.agent_data_ids, set)
