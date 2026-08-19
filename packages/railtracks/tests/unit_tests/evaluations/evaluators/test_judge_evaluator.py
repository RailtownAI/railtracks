from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from railtracks.evaluations.evaluators.judge_evaluator import (
    JudgeEvaluator,
    JudgeOutput,
    JudgeResponseSchema,
)
from railtracks.evaluations.evaluators.metrics import (
    Categorical,
    Category,
    Metric,
    Numerical,
)
from railtracks.evaluations.result import AggregateForest, MetricResult

from .conftest import make_agent_data_point


# ── helpers ───────────────────────────────────────────────────────────────────


def make_mock_llm():
    llm = MagicMock()
    llm.model_name.return_value = "mock-model"
    llm.model_provider.return_value = "MockProvider"
    return llm


HELPFULNESS = Categorical(name="Helpfulness", categories=["good", "bad"])


@pytest.fixture
def judge(mock_llm=None):
    llm = mock_llm or make_mock_llm()
    with patch("railtracks.evaluations.evaluators.judge_evaluator.rt.agent_node"):
        return JudgeEvaluator(llm=llm, metrics=[HELPFULNESS])


# ── __init__ ──────────────────────────────────────────────────────────────────


def test_init_creates_identifier(judge):
    assert isinstance(judge.identifier, str)
    assert len(judge.identifier) == 64  # sha256 hex


def test_init_name(judge):
    assert judge.name == "JudgeEvaluator"


def test_init_accepts_categorical_and_numerical_metrics(caplog):
    """Categorical and Numerical metrics are both accepted without a warning."""
    import logging
    llm = make_mock_llm()
    numerical = Numerical(name="score", min_value=0.0, max_value=10.0)
    with patch("railtracks.evaluations.evaluators.judge_evaluator.rt.agent_node"):
        with caplog.at_level(logging.WARNING):
            j = JudgeEvaluator(llm=llm, metrics=[HELPFULNESS, numerical])
    assert HELPFULNESS.identifier in j._metrics
    assert numerical.identifier in j._metrics
    assert not any("will be skipped" in r.message for r in caplog.records)


def test_init_filters_non_categorical_metrics(caplog):
    """Plain Metric (not Categorical/Numerical) generates a warning and is skipped."""
    import logging
    llm = make_mock_llm()
    base = Metric(name="some_metric")
    with patch("railtracks.evaluations.evaluators.judge_evaluator.rt.agent_node"):
        with caplog.at_level(logging.WARNING):
            j = JudgeEvaluator(llm=llm, metrics=[HELPFULNESS, base])
    assert HELPFULNESS.identifier in j._metrics
    assert base.identifier not in j._metrics
    assert any("will be skipped" in r.message for r in caplog.records)


def test_init_custom_system_prompt():
    llm = make_mock_llm()
    with patch("railtracks.evaluations.evaluators.judge_evaluator.rt.agent_node"):
        j = JudgeEvaluator(llm=llm, metrics=[HELPFULNESS], system_prompt="custom")
    assert j._system_prompt == "custom"


def test_init_default_system_prompt(judge):
    assert "evaluator" in judge._system_prompt.lower()


# ── __repr__ ──────────────────────────────────────────────────────────────────


def test_repr(judge):
    r = repr(judge)
    assert "JudgeEvaluator" in r


# ── _get_config ───────────────────────────────────────────────────────────────


def test_get_config(judge):
    config = judge._get_config()
    assert config["llm"] == "mock-model"
    assert config["llm_provider"] == "MockProvider"
    assert config["reasoning"] is True
    assert isinstance(config["metrics"], list)


def test_identifier_differs_by_reasoning():
    llm = make_mock_llm()
    with patch("railtracks.evaluations.evaluators.judge_evaluator.rt.agent_node"):
        j1 = JudgeEvaluator(llm=llm, metrics=[HELPFULNESS], reasoning=True)
        j2 = JudgeEvaluator(llm=llm, metrics=[HELPFULNESS], reasoning=False)
    assert j1.identifier != j2.identifier


# ── _generate_user_prompt ─────────────────────────────────────────────────────


def test_generate_user_prompt(judge):
    adp = make_agent_data_point()
    prompt = judge._generate_user_prompt(adp)
    assert "Agent Input" in prompt
    assert "Agent Output" in prompt


# ── _generate_system_prompt ───────────────────────────────────────────────────


def test_generate_system_prompt_with_reasoning(judge):
    prompt = judge._generate_system_prompt(HELPFULNESS)
    assert "Helpfulness" in prompt
    assert "reasoning" in prompt.lower()


def test_generate_system_prompt_without_reasoning():
    llm = make_mock_llm()
    with patch("railtracks.evaluations.evaluators.judge_evaluator.rt.agent_node"):
        j = JudgeEvaluator(llm=llm, metrics=[HELPFULNESS], reasoning=False)
    prompt = j._generate_system_prompt(HELPFULNESS)
    assert "reasoning" not in prompt.lower()


def test_generate_system_prompt_lists_category_names_with_string_input(judge):
    """HELPFULNESS is built from plain strings; the prompt must still name them."""
    prompt = judge._generate_system_prompt(HELPFULNESS)
    assert "good" in prompt
    assert "bad" in prompt
    assert "metric_value must be exactly one of these category names" in prompt


def test_generate_system_prompt_lists_category_names_with_category_object_input():
    """Same check, but the metric is built from Category objects instead of strings."""
    llm = make_mock_llm()
    metric = Categorical(
        name="Helpfulness",
        categories=[Category(name="good", status="pass"), Category(name="bad", status="fail")],
    )
    with patch("railtracks.evaluations.evaluators.judge_evaluator.rt.agent_node"):
        j = JudgeEvaluator(llm=llm, metrics=[metric])
    prompt = j._generate_system_prompt(metric)
    assert "good" in prompt
    assert "bad" in prompt
    assert "metric_value must be exactly one of these category names" in prompt
    # the internal pass/fail label must not leak into the instruction line
    instruction_line = next(
        line for line in prompt.splitlines() if "metric_value must be" in line
    )
    assert "pass" not in instruction_line
    assert "fail" not in instruction_line


def test_generate_system_prompt_numerical_bounded():
    llm = make_mock_llm()
    metric = Numerical(name="Usefulness", min_value=0, max_value=10)
    with patch("railtracks.evaluations.evaluators.judge_evaluator.rt.agent_node"):
        j = JudgeEvaluator(llm=llm, metrics=[metric])
    prompt = j._generate_system_prompt(metric)
    assert "metric_value must be a single number between 0 and 10 inclusive" in prompt


def test_generate_system_prompt_numerical_unbounded():
    llm = make_mock_llm()
    metric = Numerical(name="Usefulness")
    with patch("railtracks.evaluations.evaluators.judge_evaluator.rt.agent_node"):
        j = JudgeEvaluator(llm=llm, metrics=[metric])
    prompt = j._generate_system_prompt(metric)
    assert "metric_value must be a single number" in prompt


def test_generate_system_prompt_numerical_with_shots():
    llm = make_mock_llm()
    metric = Numerical(
        name="Usefulness",
        min_value=0,
        max_value=10,
        shots=[
            (0, "not useful at all"),
            (5, "somewhat useful"),
            (10, "extremely useful"),
        ],
    )
    with patch("railtracks.evaluations.evaluators.judge_evaluator.rt.agent_node"):
        j = JudgeEvaluator(llm=llm, metrics=[metric])
    prompt = j._generate_system_prompt(metric)
    assert "not useful at all" in prompt
    assert "somewhat useful" in prompt
    assert "extremely useful" in prompt
    assert "interpolate" in prompt.lower()


# ── _aggregate_metrics ────────────────────────────────────────────────────────


def test_aggregate_metrics_categorical(judge):
    adp_id = uuid4()
    metric = HELPFULNESS
    forest = AggregateForest()
    mr = MetricResult(
        result_name="JudgeResult/Helpfulness",
        metric_id=metric.identifier,
        agent_data_id=[adp_id],
        value="good",
    )
    forest.add_node(mr)
    results = {metric: [mr]}
    judge._aggregate_metrics(results, forest)
    assert len(forest.roots) == 1


def test_aggregate_metrics_skips_base_metric(judge):
    """Plain Metric (not Categorical/Numerical) should produce no aggregate root."""
    adp_id = uuid4()
    base_metric = Metric(name="reasoning_metric")
    forest = AggregateForest()
    mr = MetricResult(
        result_name="reasoning",
        metric_id=base_metric.identifier,
        agent_data_id=[adp_id],
        value="because...",
    )
    forest.add_node(mr)
    results = {base_metric: [mr]}
    judge._aggregate_metrics(results, forest)
    assert len(forest.roots) == 0


# ── run (via mocked _invoke) ──────────────────────────────────────────────────


def _mock_invoke(judge_instance, adp, metric):
    return [JudgeOutput(metric.identifier, str(adp.identifier), JudgeResponseSchema(metric_value="good", reasoning="looks good"))]


def test_run_returns_evaluator_result(judge):
    adp = make_agent_data_point()
    with patch.object(judge, "_invoke", return_value=_mock_invoke(judge, adp, HELPFULNESS)):
        result = judge.run([adp])
    assert result.evaluator_name == "JudgeEvaluator"
    assert len(result.metric_results) >= 1


def test_run_includes_reasoning_result(judge):
    adp = make_agent_data_point()
    with patch.object(judge, "_invoke", return_value=_mock_invoke(judge, adp, HELPFULNESS)):
        result = judge.run([adp])
    names = [r.result_name for r in result.metric_results]
    assert any("JudgeResult" in n for n in names)
    assert any("JudgeReasoning" in n for n in names)


def test_run_no_reasoning_when_disabled():
    llm = make_mock_llm()
    with patch("railtracks.evaluations.evaluators.judge_evaluator.rt.agent_node"):
        j = JudgeEvaluator(llm=llm, metrics=[HELPFULNESS], reasoning=False)
    adp = make_agent_data_point()
    fake_output = [JudgeOutput(HELPFULNESS.identifier, str(adp.identifier), JudgeResponseSchema(metric_value="good"))]
    with patch.object(j, "_invoke", return_value=fake_output):
        result = j.run([adp])
    names = [r.result_name for r in result.metric_results]
    assert not any("Reasoning" in n for n in names)


def test_run_reasoning_none_does_not_add_result(judge):
    """When reasoning is enabled but judge returns None reasoning, no reasoning result added."""
    adp = make_agent_data_point()
    fake_output = [JudgeOutput(HELPFULNESS.identifier, str(adp.identifier), JudgeResponseSchema(metric_value="good", reasoning=None))]
    with patch.object(judge, "_invoke", return_value=fake_output):
        result = judge.run([adp])
    names = [r.result_name for r in result.metric_results]
    assert not any("Reasoning" in n for n in names)


def test_run_agent_data_ids(judge):
    adp = make_agent_data_point()
    with patch.object(judge, "_invoke", return_value=_mock_invoke(judge, adp, HELPFULNESS)):
        result = judge.run([adp])
    assert adp.identifier in result.agent_data_ids


def test_run_numerical_metric():
    """A Numerical metric produces a numerical MetricResult."""
    llm = make_mock_llm()
    metric = Numerical(name="Usefulness", min_value=0, max_value=10)
    with patch("railtracks.evaluations.evaluators.judge_evaluator.rt.agent_node"):
        j = JudgeEvaluator(llm=llm, metrics=[metric])
    adp = make_agent_data_point()
    fake_output = [
        JudgeOutput(
            metric.identifier,
            str(adp.identifier),
            JudgeResponseSchema(metric_value=7, reasoning="decent"),
        )
    ]
    with patch.object(j, "_invoke", return_value=fake_output):
        result = j.run([adp])
    values = [
        r.value for r in result.metric_results if r.result_name.startswith("JudgeResult")
    ]
    assert values == [7]
