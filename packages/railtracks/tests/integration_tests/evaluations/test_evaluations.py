import json
from uuid import UUID

import pytest

from railtracks.evaluations.evaluators.llm_inference_evaluator import LLMInferenceEvaluator
from railtracks.evaluations.evaluators.tool_use_evaluator import ToolUseEvaluator
from railtracks.evaluations.point import AgentDataPoint, extract_agent_data_points
from railtracks.evaluations.result import EvaluationResult
from railtracks.evaluations.runners._evaluate import evaluate
from railtracks.evaluations.utils import payload

from .conftest import AGENT_ID_1, AGENT_ID_2, SESSION_ID_1, SESSION_ID_2, make_session_dict


# ── Session file → AgentDataPoint data integrity ──────────────────────────────


def test_correct_llm_values_extracted_from_session(session_file):
    """Values written into the session JSON reach the AgentDataPoint unchanged."""
    adps = extract_agent_data_points(str(session_file))
    call = adps[0].llm_details.calls[0]
    assert call.model_name == "gpt-4"
    assert call.model_provider == "OpenAI"
    assert call.input_tokens == 50
    assert call.output_tokens == 10
    assert call.total_cost == pytest.approx(0.001)
    assert call.latency == pytest.approx(1.2)


def test_correct_tool_values_extracted_from_session(session_file):
    """Tool name and runtime from the session JSON are reflected in the AgentDataPoint."""
    adps = extract_agent_data_points(str(session_file))
    assert "get_stock_price" in adps[0].tool_details.tool_names
    call = adps[0].tool_details.calls[0]
    assert call.name == "get_stock_price"
    assert call.runtime == pytest.approx(0.1)


def test_agent_io_extracted_from_session(session_file):
    """Agent input and output are parsed from the session edge details."""
    adps = extract_agent_data_points(str(session_file))
    assert "What is the stock price?" in adps[0].agent_input["args"]
    assert adps[0].agent_output == {"answer": "The stock is $100."}


def test_session_and_agent_ids_preserved(session_file):
    """UUIDs from the session file are faithfully stored on the AgentDataPoint."""
    adps = extract_agent_data_points(str(session_file))
    assert adps[0].session_id == UUID(SESSION_ID_1)
    assert adps[0].identifier == UUID(AGENT_ID_1)


def test_directory_ingestion_yields_one_adp_per_file(session_dir):
    """Passing a directory extracts one AgentDataPoint per session file."""
    adps = extract_agent_data_points(str(session_dir))
    assert len(adps) == 2
    session_ids = {adp.session_id for adp in adps}
    assert session_ids == {UUID(SESSION_ID_1), UUID(SESSION_ID_2)}


# ── LLMInferenceEvaluator: session → metric values ───────────────────────────


def test_llm_evaluator_input_token_values_match_session(two_session_files):
    """InputToken metric results reflect the token counts in the session files."""
    adps = extract_agent_data_points([str(p) for p in two_session_files])
    result = LLMInferenceEvaluator().run(adps)
    token_results = [r for r in result.metric_results if r.result_name == "InputTokens"]
    assert all(r.value == 50 for r in token_results)


def test_llm_evaluator_latency_values_match_session(two_session_files):
    """Latency metric results reflect the latency values in the session files."""
    adps = extract_agent_data_points([str(p) for p in two_session_files])
    result = LLMInferenceEvaluator().run(adps)
    latency_results = [r for r in result.metric_results if r.result_name == "Latency"]
    assert all(r.value == pytest.approx(1.2) for r in latency_results)


def test_llm_evaluator_aggregate_mean_reflects_session_values(two_session_files):
    """The aggregate mean for a metric equals the value from the session (same value in both runs)."""
    adps = extract_agent_data_points([str(p) for p in two_session_files])
    result = LLMInferenceEvaluator().run(adps)
    forest = result.aggregate_results
    for root_id in forest.roots:
        node = forest.get(root_id)
        if "InputTokens" in node.name:
            assert node.mean == pytest.approx(50.0)
            assert node.minimum == 50
            assert node.maximum == 50
            break
    else:
        pytest.fail("No InputTokens aggregate node found")


def test_llm_evaluator_agent_data_ids_match_extracted_adps(two_session_files):
    """The evaluator result's agent_data_ids correspond to the extracted AgentDataPoints."""
    adps = extract_agent_data_points([str(p) for p in two_session_files])
    result = LLMInferenceEvaluator().run(adps)
    assert result.agent_data_ids == {adp.identifier for adp in adps}


# ── ToolUseEvaluator: session → metric values ─────────────────────────────────


def test_tool_evaluator_failure_rate_zero_for_healthy_runs(two_session_files):
    """FailureRate is 0.0 when all tool calls in the session files are Completed."""
    adps = extract_agent_data_points([str(p) for p in two_session_files])
    result = ToolUseEvaluator().run(adps)
    failure_rates = [r for r in result.metric_results if r.result_name.startswith("FailureRate")]
    assert all(r.value == pytest.approx(0.0) for r in failure_rates)


def test_tool_evaluator_failure_rate_propagates_from_failed_session(tmp_path):
    """A Failed tool edge in one session causes a non-zero FailureRate in the result."""
    f1 = tmp_path / "s1.json"
    f2 = tmp_path / "s2.json"
    f1.write_text(
        json.dumps(
            make_session_dict(
                agent_id=AGENT_ID_1,
                tool_id="bbbbbbbb-0000-0000-0000-000000000001",
                session_id=SESSION_ID_1,
                tool_status="Failed",
            )
        )
    )
    f2.write_text(
        json.dumps(
            make_session_dict(
                agent_id=AGENT_ID_2,
                tool_id="bbbbbbbb-0000-0000-0000-000000000002",
                session_id=SESSION_ID_2,
            )
        )
    )
    adps = extract_agent_data_points([str(f1), str(f2)])
    result = ToolUseEvaluator().run(adps)
    failure_rates = [r for r in result.metric_results if r.result_name.startswith("FailureRate")]
    assert 1.0 in [r.value for r in failure_rates]


def test_tool_evaluator_runtime_values_match_session(two_session_files):
    """Runtime metric results reflect the tool latency stored in the session files."""
    adps = extract_agent_data_points([str(p) for p in two_session_files])
    result = ToolUseEvaluator().run(adps)
    runtime_results = [r for r in result.metric_results if r.result_name.startswith("Runtime")]
    assert all(r.value == pytest.approx(0.1) for r in runtime_results)


# ── evaluate(): cross-component wiring ───────────────────────────────────────


def test_evaluate_with_real_evaluators_returns_evaluation_results(two_session_files):
    """Full pipeline with real evaluators produces a list of EvaluationResult."""
    adps = extract_agent_data_points([str(p) for p in two_session_files])
    results = evaluate(adps, [LLMInferenceEvaluator(), ToolUseEvaluator()], agent_selection=False)
    assert len(results) == 1
    assert isinstance(results[0], EvaluationResult)


def test_evaluate_evaluator_results_wired_into_evaluation_result(two_session_files):
    """Both evaluator results are stored on the EvaluationResult."""
    adps = extract_agent_data_points([str(p) for p in two_session_files])
    results = evaluate(adps, [LLMInferenceEvaluator(), ToolUseEvaluator()], agent_selection=False)
    evaluator_names = {er.evaluator_name for er in results[0].evaluator_results}
    assert evaluator_names == {"LLMInferenceEvaluator", "ToolUseEvaluator"}


def test_evaluate_metrics_map_contains_all_metrics(two_session_files):
    """The EvaluationResult metrics_map aggregates metrics from all evaluators."""
    adps = extract_agent_data_points([str(p) for p in two_session_files])
    results = evaluate(adps, [LLMInferenceEvaluator(), ToolUseEvaluator()], agent_selection=False)
    metric_names = {m.name for m in results[0].metrics_map.values()}
    assert "InputTokens" in metric_names
    assert "Runtime" in metric_names


def test_evaluate_agent_node_ids_reference_extracted_adps(two_session_files):
    """The agent_node_ids in the result correspond to the extracted AgentDataPoints."""
    adps = extract_agent_data_points([str(p) for p in two_session_files])
    results = evaluate(adps, [LLMInferenceEvaluator()], agent_selection=False)
    node_ids = {
        entry["agent_node_id"]
        for entry in results[0].agents[0]["agent_node_ids"]
    }
    adp_ids = {adp.identifier for adp in adps}
    assert node_ids == adp_ids


def test_evaluate_multi_agent_filter_via_agents_param(tmp_path):
    """With two differently-named agents, the agents= filter routes to the right one."""
    f1 = tmp_path / "s1.json"
    f2 = tmp_path / "s2.json"
    f1.write_text(
        json.dumps(
            make_session_dict(
                agent_id=AGENT_ID_1,
                tool_id="bbbbbbbb-0000-0000-0000-000000000001",
                session_id=SESSION_ID_1,
                agent_name="AgentAlpha",
            )
        )
    )
    f2.write_text(
        json.dumps(
            make_session_dict(
                agent_id=AGENT_ID_2,
                tool_id="bbbbbbbb-0000-0000-0000-000000000002",
                session_id=SESSION_ID_2,
                agent_name="AgentBeta",
            )
        )
    )
    adps = extract_agent_data_points([str(f1), str(f2)])
    results = evaluate(adps, [LLMInferenceEvaluator()], agent_selection=False, agents=["AgentAlpha"])
    assert len(results) == 1
    assert results[0].agents[0]["agent_name"] == "AgentAlpha"


# ── evaluate() → payload() round-trip ────────────────────────────────────────


def test_payload_from_real_result_is_json_serializable(two_session_files):
    """A payload built from a real evaluation pipeline is fully JSON-serializable."""
    adps = extract_agent_data_points([str(p) for p in two_session_files])
    results = evaluate(adps, [LLMInferenceEvaluator(), ToolUseEvaluator()], agent_selection=False)
    p = payload(results[0])
    dumped = json.dumps(p)  # must not raise
    restored = json.loads(dumped)
    assert restored["evaluation_id"] == str(results[0].evaluation_id)
    assert len(restored["evaluator_results"]) == 2


def test_payload_callback_receives_real_result_dict(two_session_files):
    """The payload_callback is invoked with the real serialized result dictionary."""
    adps = extract_agent_data_points([str(p) for p in two_session_files])
    received: list[dict] = []
    evaluate(
        adps,
        [LLMInferenceEvaluator()],
        agent_selection=False,
        payload_callback=received.append,
    )
    assert len(received) == 1
    assert "evaluation_id" in received[0]
    assert "evaluator_results" in received[0]
