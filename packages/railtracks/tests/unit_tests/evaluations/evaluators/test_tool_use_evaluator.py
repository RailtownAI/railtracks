import pytest

from railtracks.evaluations.evaluators.tool_use_evaluator import ToolUseEvaluator
from railtracks.evaluations.point import Status

from .conftest import make_agent_data_point, make_tool_call


# ── ToolUseEvaluator ──────────────────────────────────────────────────────────


def test_run_returns_expected_metrics(two_agent_data_points):
    result = ToolUseEvaluator().run(two_agent_data_points)
    metric_names = {m.name for m in result.metrics}
    assert {"ToolFailure", "Runtime", "FailureRate", "UsageCount"}.issubset(metric_names)


def test_run_agent_data_ids_populated(two_agent_data_points):
    result = ToolUseEvaluator().run(two_agent_data_points)
    ids = {adp.identifier for adp in two_agent_data_points}
    assert ids == result.agent_data_ids


def test_run_usage_count_correct(two_agent_data_points):
    result = ToolUseEvaluator().run(two_agent_data_points)
    usage_results = [r for r in result.metric_results if r.result_name.startswith("UsageCount")]
    assert all(r.value == 1 for r in usage_results)


def test_run_failure_rate_zero_when_all_completed(two_agent_data_points):
    result = ToolUseEvaluator().run(two_agent_data_points)
    failure_rates = [r for r in result.metric_results if r.result_name.startswith("FailureRate")]
    assert all(r.value == 0.0 for r in failure_rates)


def test_run_failure_rate_nonzero_when_tool_fails():
    failed = make_tool_call(name="get_price", status=Status.FAILED)
    adp = make_agent_data_point(tool_calls=[failed])
    result = ToolUseEvaluator().run([adp])
    failure_rates = [r for r in result.metric_results if r.result_name.startswith("FailureRate")]
    values = [r.value for r in failure_rates]
    assert 1.0 in values


def test_run_runtime_results_use_tool_runtime(two_agent_data_points):
    result = ToolUseEvaluator().run(two_agent_data_points)
    runtime_results = [r for r in result.metric_results if r.result_name.startswith("Runtime")]
    assert all(r.value == pytest.approx(0.1) for r in runtime_results)


def test_run_aggregate_forest_has_roots(two_agent_data_points):
    result = ToolUseEvaluator().run(two_agent_data_points)
    assert len(result.aggregate_results.roots) > 0


def test_run_single_data_point_single_tool_call():
    adp = make_agent_data_point(tool_calls=[make_tool_call(name="get_price")])
    result = ToolUseEvaluator().run([adp])
    metric_names = {m.name for m in result.metrics}
    assert {"ToolFailure", "Runtime", "FailureRate", "UsageCount"}.issubset(metric_names)
    assert len(result.aggregate_results.roots) > 0


def test_run_single_data_point_multiple_calls_same_tool():
    adp = make_agent_data_point(
        tool_calls=[
            make_tool_call(name="get_price", runtime=0.1),
            make_tool_call(name="get_price", runtime=0.3),
            make_tool_call(name="get_price", runtime=0.5),
        ]
    )
    result = ToolUseEvaluator().run([adp])

    usage = [r for r in result.metric_results if r.result_name.startswith("UsageCount")]
    assert [r.value for r in usage] == [3]

    runtimes = {r.value for r in result.metric_results if r.result_name.startswith("Runtime")}
    assert runtimes == {0.1, 0.3, 0.5}


def test_run_multiple_tools():
    tool_a = make_tool_call(name="tool_a", runtime=0.1)
    tool_b = make_tool_call(name="tool_b", runtime=0.5)
    adp1 = make_agent_data_point(tool_calls=[tool_a, tool_b])
    adp2 = make_agent_data_point(tool_calls=[tool_a, tool_b])
    result = ToolUseEvaluator().run([adp1, adp2])
    tool_names_in_results = {r.tool_name for r in result.metric_results}
    assert "tool_a" in tool_names_in_results
    assert "tool_b" in tool_names_in_results
