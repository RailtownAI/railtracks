from railtracks.evaluations.evaluators.llm_inference_evaluator import LLMInferenceEvaluator
from railtracks.evaluations.result import LLMMetricResult

from .conftest import make_agent_data_point, make_llm_call


# ── LLMInferenceEvaluator ─────────────────────────────────────────────────────


def test_run_returns_four_metrics_per_llm_call():
    adp = make_agent_data_point(llm_calls=[make_llm_call(index=0)])
    result = LLMInferenceEvaluator().run([adp])
    metric_names = {m.name for m in result.metrics}
    assert metric_names == {"InputTokens", "OutputTokens", "TokenCost", "Latency"}


def test_run_result_count_matches_calls(agent_data_point):
    # 1 data point × 1 llm call × 4 metrics = 4 results
    result = LLMInferenceEvaluator().run([agent_data_point])
    assert len(result.metric_results) == 4


def test_run_multiple_llm_calls():
    adp = make_agent_data_point(llm_calls=[make_llm_call(index=0), make_llm_call(index=1)])
    result = LLMInferenceEvaluator().run([adp])
    # 2 calls × 4 metrics = 8 results
    assert len(result.metric_results) == 8


def test_run_result_values_correct():
    call = make_llm_call(input_tokens=100, output_tokens=20, total_cost=0.005, latency=2.5)
    adp = make_agent_data_point(llm_calls=[call])
    result = LLMInferenceEvaluator().run([adp])
    by_name = {r.result_name: r.value for r in result.metric_results}
    assert by_name["InputTokens"] == 100
    assert by_name["OutputTokens"] == 20
    assert by_name["TokenCost"] == 0.005
    assert by_name["Latency"] == 2.5


def test_run_all_results_are_llm_metric_results(agent_data_point):
    result = LLMInferenceEvaluator().run([agent_data_point])
    assert all(isinstance(r, LLMMetricResult) for r in result.metric_results)


def test_run_agent_data_ids_populated(agent_data_point):
    result = LLMInferenceEvaluator().run([agent_data_point])
    assert agent_data_point.identifier in result.agent_data_ids


def test_run_aggregate_forest_has_roots(agent_data_point):
    result = LLMInferenceEvaluator().run([agent_data_point])
    assert len(result.aggregate_results.roots) > 0


def test_run_no_llm_calls():
    adp = make_agent_data_point(llm_calls=[])
    result = LLMInferenceEvaluator().run([adp])
    assert result.metric_results == []
    assert result.metrics == []
