from uuid import UUID

from railtracks.evaluation.evaluators.judge_evaluator import (
    JudgeEvaluator,
    JudgeResponseSchema,
    JudgeMetricResult,
)
from railtracks.evaluation.evaluators.metrics import Numerical
from railtracks.evaluation.result import EvaluatorResult
from railtracks.utils.point import AgentDataPoint


# ================= Schema Validation Tests =================


def test_judge_metric_result_validation():
    """Test JudgeMetricResult schema validation."""
    result = JudgeMetricResult(
        metric_name="Sentiment",
        metric_value="Positive"
    )
    
    assert result.metric_name == "Sentiment"
    assert result.metric_value == "Positive"


def test_judge_metric_result_with_string_value():
    """Test JudgeMetricResult with string value."""
    result = JudgeMetricResult(
        metric_name="Category",
        metric_value="Excellent"
    )
    
    assert isinstance(result.metric_value, str)
    assert result.metric_value == "Excellent"


def test_judge_metric_result_with_numeric_value():
    """Test JudgeMetricResult with numeric values."""
    result_float = JudgeMetricResult(
        metric_name="Accuracy",
        metric_value=0.95
    )
    result_int = JudgeMetricResult(
        metric_name="Count",
        metric_value=42
    )
    
    assert result_float.metric_value == 0.95
    assert result_int.metric_value == 42


def test_judge_response_schema_with_results():
    """Test JudgeResponseSchema with metric results."""
    response = JudgeResponseSchema(
        metric_results=[
            JudgeMetricResult(metric_name="Sentiment", metric_value="Positive")
        ],
        reasoning="Test reasoning"
    )
    
    assert len(response.metric_results) == 1
    assert response.metric_results[0].metric_name == "Sentiment"
    assert response.reasoning == "Test reasoning"


def test_judge_response_schema_with_multiple_results():
    """Test JudgeResponseSchema with multiple metric results."""
    response = JudgeResponseSchema(
        metric_results=[
            JudgeMetricResult(metric_name="Sentiment", metric_value="Positive"),
            JudgeMetricResult(metric_name="Accuracy", metric_value=0.92),
            JudgeMetricResult(metric_name="Helpfulness", metric_value="Helpful"),
        ],
        reasoning="Comprehensive evaluation"
    )
    
    assert len(response.metric_results) == 3
    assert response.metric_results[0].metric_name == "Sentiment"
    assert response.metric_results[1].metric_name == "Accuracy"
    assert response.metric_results[2].metric_name == "Helpfulness"


def test_judge_response_schema_with_null_results():
    """Test JudgeResponseSchema handles null metric_results."""
    response = JudgeResponseSchema(
        metric_results=None,
        reasoning="Test reasoning"
    )
    
    assert response.metric_results is None
    assert response.reasoning == "Test reasoning"


def test_judge_response_schema_with_null_reasoning():
    """Test JudgeResponseSchema handles null reasoning."""
    response = JudgeResponseSchema(
        metric_results=[
            JudgeMetricResult(metric_name="Sentiment", metric_value="Positive")
        ],
        reasoning=None
    )
    
    assert len(response.metric_results) == 1
    assert response.reasoning is None


def test_judge_response_schema_all_null():
    """Test JudgeResponseSchema with all optional fields as null."""
    response = JudgeResponseSchema(
        metric_results=None,
        reasoning=None
    )
    
    assert response.metric_results is None
    assert response.reasoning is None


def test_judge_response_schema_json_serialization():
    """Test JudgeResponseSchema can be serialized to JSON."""
    response = JudgeResponseSchema(
        metric_results=[
            JudgeMetricResult(metric_name="Sentiment", metric_value="Positive"),
            JudgeMetricResult(metric_name="Score", metric_value=8.5),
        ],
        reasoning="Detailed reasoning here"
    )
    
    json_data = response.model_dump(mode="json")
    
    assert "metric_results" in json_data
    assert "reasoning" in json_data
    assert len(json_data["metric_results"]) == 2


def test_judge_response_schema_from_dict():
    """Test JudgeResponseSchema can be created from dictionary."""
    data = {
        "metric_results": [
            {"metric_name": "Sentiment", "metric_value": "Negative"}
        ],
        "reasoning": "Analysis complete"
    }
    
    response = JudgeResponseSchema.model_validate(data)
    
    assert len(response.metric_results) == 1
    assert response.metric_results[0].metric_name == "Sentiment"
    assert response.reasoning == "Analysis complete"


def test_judge_metric_result_from_dict():
    """Test JudgeMetricResult can be created from dictionary."""
    data = {
        "metric_name": "Quality",
        "metric_value": "High"
    }
    
    result = JudgeMetricResult.model_validate(data)
    
    assert result.metric_name == "Quality"
    assert result.metric_value == "High"


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
    assert evaluator._metrics[0].name == "Sentiment"
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
    assert custom_prompt in evaluator._system_prompt


def test_judge_evaluator_initialization_with_multiple_metrics(multiple_metrics, mock_llm):
    """Test JudgeEvaluator initialization with multiple metrics."""
    llm = mock_llm()
    evaluator = JudgeEvaluator(
        llm=llm,
        metrics=multiple_metrics,
    )
    
    assert len(evaluator._metrics) == 3
    assert evaluator._metrics[0].name == "Sentiment"
    assert evaluator._metrics[1].name == "Accuracy"
    assert evaluator._metrics[2].name == "Helpfulness"


def test_judge_evaluator_creates_metrics_dict(sample_categorical_metric, mock_llm):
    """Test that JudgeEvaluator creates a metrics dictionary."""
    llm = mock_llm()
    evaluator = JudgeEvaluator(
        llm=llm,
        metrics=[sample_categorical_metric],
    )
    
    assert "Sentiment" in evaluator._metrics_dict
    assert evaluator._metrics_dict["Sentiment"] == sample_categorical_metric


# ================= System Prompt Generation Tests =================


def test_generate_system_prompt_with_default(sample_categorical_metric, mock_llm):
    """Test system prompt generation with default prompt."""
    llm = mock_llm()
    evaluator = JudgeEvaluator(
        llm=llm,
        metrics=[sample_categorical_metric],
    )
    
    assert "expert evaluator" in evaluator._system_prompt.lower()
    assert "Sentiment" in evaluator._system_prompt


def test_generate_system_prompt_with_custom_prompt(sample_categorical_metric, mock_llm):
    """Test system prompt generation with custom prompt."""
    llm = mock_llm()
    custom_prompt = "Custom evaluator prompt"
    
    evaluator = JudgeEvaluator(
        llm=llm,
        metrics=[sample_categorical_metric],
        system_prompt=custom_prompt,
    )
    
    assert custom_prompt in evaluator._system_prompt
    assert "Sentiment" in evaluator._system_prompt


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
    
    assert "reasoning" in evaluator_with_reasoning._system_prompt.lower()
    assert "reasoning" not in evaluator_without_reasoning._system_prompt.lower()


def test_generate_system_prompt_includes_metrics(multiple_metrics, mock_llm):
    """Test system prompt includes all metrics."""
    llm = mock_llm()
    evaluator = JudgeEvaluator(
        llm=llm,
        metrics=multiple_metrics,
    )
    
    assert "Sentiment" in evaluator._system_prompt
    assert "Accuracy" in evaluator._system_prompt
    assert "Helpfulness" in evaluator._system_prompt


# ================= Metrics String Generation Tests =================


def test_metrics_str_with_single_metric(sample_categorical_metric, mock_llm):
    """Test _metrics_str with a single metric."""
    llm = mock_llm()
    evaluator = JudgeEvaluator(
        llm=llm,
        metrics=[sample_categorical_metric],
    )
    
    metrics_str = evaluator._metrics_str()
    
    assert "Sentiment" in metrics_str
    assert not metrics_str.endswith("\n")


def test_metrics_str_with_multiple_metrics(multiple_metrics, mock_llm):
    """Test _metrics_str with multiple metrics."""
    llm = mock_llm()
    evaluator = JudgeEvaluator(
        llm=llm,
        metrics=multiple_metrics,
    )
    
    metrics_str = evaluator._metrics_str()
    
    assert "Sentiment" in metrics_str
    assert "Accuracy" in metrics_str
    assert "Helpfulness" in metrics_str
    lines = metrics_str.split("\n")
    assert len(lines) == 3


def test_metrics_str_with_no_metrics(mock_llm):
    """Test _metrics_str with no metrics returns empty string."""
    llm = mock_llm()
    evaluator = JudgeEvaluator(
        llm=llm,
        metrics=[],
    )
    
    metrics_str = evaluator._metrics_str()
    
    assert metrics_str == ""


# ================= Prompt Template Tests =================


def test_prompt_template_formats_data_point(sample_categorical_metric, sample_data_points, mock_llm):
    """Test _prompt_template correctly formats a data point."""
    llm = mock_llm()
    evaluator = JudgeEvaluator(
        llm=llm,
        metrics=[sample_categorical_metric],
    )
    
    data_point = sample_data_points[0]
    prompt = evaluator._prompt_template(data_point)
    
    assert str(data_point.agent_input) in prompt
    assert str(data_point.agent_output) in prompt


def test_prompt_template_handles_none_internals(sample_categorical_metric, mock_llm):
    """Test _prompt_template handles None agent_internals."""
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
    
    prompt = evaluator._prompt_template(data_point)
    
    assert "Agent Input:" in prompt
    assert "Agent Output:" in prompt
    assert "{}" in prompt  # Empty dict for internals


def test_prompt_template_includes_internals(sample_categorical_metric, mock_llm):
    """Test _prompt_template includes agent internals when present."""
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
    
    prompt = evaluator._prompt_template(data_point)
    
    assert "steps" in prompt or str(data_point.agent_internals) in prompt


# ================= Aggregate Metrics Tests =================


def test_aggregate_metrics_with_categorical(sample_categorical_metric, mock_llm):
    """Test _aggregate_metrics creates aggregate for categorical metrics."""
    llm = mock_llm()
    evaluator = JudgeEvaluator(
        llm=llm,
        metrics=[sample_categorical_metric],
    )
    
    aggregates = evaluator._aggregate_metrics()
    
    assert len(aggregates) == 1
    assert aggregates[0].metric == sample_categorical_metric


def test_aggregate_metrics_with_numerical(sample_numerical_metric, mock_llm):
    """Test _aggregate_metrics skips numerical metrics."""
    llm = mock_llm()
    evaluator = JudgeEvaluator(
        llm=llm,
        metrics=[sample_numerical_metric],
    )
    
    aggregates = evaluator._aggregate_metrics()
    
    assert len(aggregates) == 0


def test_aggregate_metrics_with_mixed_metrics(multiple_metrics, mock_llm):
    """Test _aggregate_metrics with mixed metric types."""
    llm = mock_llm()
    evaluator = JudgeEvaluator(
        llm=llm,
        metrics=multiple_metrics,
    )
    
    aggregates = evaluator._aggregate_metrics()
    
    # Should only aggregate categorical metrics (Sentiment and Helpfulness)
    assert len(aggregates) == 2


# ================= Run Method Tests =================
# Note: Actual .run() tests require real LLM integration and belong in integration tests


# ================= Repr Tests =================


def test_repr_includes_all_parameters(sample_categorical_metric, mock_llm):
    """Test __repr__ includes all initialization parameters."""
    llm = mock_llm()
    evaluator = JudgeEvaluator(
        llm=llm,
        metrics=[sample_categorical_metric],
        system_prompt="Custom prompt",
        reasoning=False,
    )
    
    repr_str = repr(evaluator)
    
    assert "JudgeEvaluator" in repr_str
    assert "system_prompt" in repr_str
    assert "llm" in repr_str
    assert "metric" in repr_str
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


# ================= Config Hash Tests =================


def test_config_hash_is_deterministic(sample_categorical_metric, mock_llm):
    """Test that config hash is deterministic for same configuration."""
    llm = mock_llm()
    
    evaluator1 = JudgeEvaluator(
        llm=llm,
        metrics=[sample_categorical_metric],
        system_prompt="Same prompt",
        reasoning=True,
    )
    
    evaluator2 = JudgeEvaluator(
        llm=llm,
        metrics=[sample_categorical_metric],
        system_prompt="Same prompt",
        reasoning=True,
    )
    
    # Same configuration should produce same hash
    assert evaluator1.config_hash == evaluator2.config_hash


def test_config_hash_differs_for_different_configs(sample_categorical_metric, mock_llm):
    """Test that config hash differs for different configurations."""
    llm = mock_llm()
    
    evaluator1 = JudgeEvaluator(
        llm=llm,
        metrics=[sample_categorical_metric],
        reasoning=True,
    )
    
    evaluator2 = JudgeEvaluator(
        llm=llm,
        metrics=[sample_categorical_metric],
        reasoning=False,
    )
    
    # Different configurations should produce different hashes
    assert evaluator1.config_hash != evaluator2.config_hash


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


# ================= Integration Tests =================
# Note: These require real LLM integration and belong in integration test suite


# ================= Edge Cases =================


def test_evaluator_with_empty_metrics_list(mock_llm):
    """Test evaluator with empty metrics list."""
    llm = mock_llm()
    evaluator = JudgeEvaluator(
        llm=llm,
        metrics=[],
    )
    
    assert len(evaluator._metrics) == 0
    assert evaluator._metrics_str() == ""


def test_evaluator_copies_metrics_list(sample_categorical_metric, mock_llm):
    """Test that evaluator creates a copy of the metrics list."""
    llm = mock_llm()
    original_metrics = [sample_categorical_metric]
    
    evaluator = JudgeEvaluator(
        llm=llm,
        metrics=original_metrics,
    )
    
    # Modify original list
    original_metrics.append(Numerical(name="NewMetric"))
    
    # Evaluator's metrics should not be affected
    assert len(evaluator._metrics) == 1
