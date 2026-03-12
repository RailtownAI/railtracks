from unittest.mock import MagicMock, patch

import pytest
from railtracks.evaluations.evaluators.evaluator import Evaluator
from railtracks.evaluations.result import AggregateForest, EvaluatorResult
from railtracks.evaluations.runners._evaluate import (
    _check_evaluators,
    _setup_agent_data,
    evaluate,
)

from ..evaluations.evaluators.conftest import make_agent_data_point

# ── Helpers ───────────────────────────────────────────────────────────────────


def make_evaluator(identifier: str = "eval-id-1", name: str = "MockEvaluator") -> MagicMock:
    ev = MagicMock(spec=Evaluator)
    ev.identifier = identifier
    ev.name = name
    ev.run.return_value = EvaluatorResult(
        evaluator_name=name,
        evaluator_id=identifier,
        metrics=[],
        metric_results=[],
        aggregate_results=AggregateForest(),
    )
    return ev


# ── _check_evaluators ─────────────────────────────────────────────────────────


def test_check_evaluators_no_duplicates_no_warning(caplog):
    ev1 = make_evaluator("id-1", "Ev1")
    ev2 = make_evaluator("id-2", "Ev2")
    _check_evaluators([ev1, ev2])
    assert "duplicated" not in caplog.text


def test_check_evaluators_duplicate_logs_warning(caplog):
    ev1 = make_evaluator("same-id", "EvalA")
    ev2 = make_evaluator("same-id", "EvalA")
    with caplog.at_level("WARNING"):
        _check_evaluators([ev1, ev2])
    assert "duplicated" in caplog.text


def test_check_evaluators_empty_list():
    # Should not raise
    _check_evaluators([])


def test_check_evaluators_single_evaluator_no_warning(caplog):
    ev = make_evaluator()
    _check_evaluators([ev])
    assert "duplicated" not in caplog.text


# ── _setup_agent_data ─────────────────────────────────────────────────────────


def test_setup_agent_data_single_adp():
    adp = make_agent_data_point(agent_name="AgentA")
    data_dict, agents = _setup_agent_data(adp, agent_selection=False, agents=None)
    assert "AgentA" in data_dict
    assert data_dict["AgentA"] == [adp]
    assert agents == ["AgentA"]


def test_setup_agent_data_list_of_adps():
    adp1 = make_agent_data_point(agent_name="AgentA")
    adp2 = make_agent_data_point(agent_name="AgentA")
    data_dict, agents = _setup_agent_data([adp1, adp2], agent_selection=False, agents=None)
    assert len(data_dict["AgentA"]) == 2


def test_setup_agent_data_multiple_agents_no_selection():
    adp_a = make_agent_data_point(agent_name="AgentA")
    adp_b = make_agent_data_point(agent_name="AgentB")
    data_dict, agents = _setup_agent_data([adp_a, adp_b], agent_selection=False, agents=None)
    assert set(agents) == {"AgentA", "AgentB"}


def test_setup_agent_data_agents_filter():
    adp_a = make_agent_data_point(agent_name="AgentA")
    adp_b = make_agent_data_point(agent_name="AgentB")
    data_dict, agents = _setup_agent_data(
        [adp_a, adp_b], agent_selection=False, agents=["AgentA"]
    )
    assert agents == ["AgentA"]
    assert "AgentB" not in agents


def test_setup_agent_data_agents_filter_missing_warns(caplog):
    adp_a = make_agent_data_point(agent_name="AgentA")
    with caplog.at_level("WARNING"):
        data_dict, agents = _setup_agent_data(
            [adp_a], agent_selection=False, agents=["AgentA", "Missing"]
        )
    assert "Missing" in caplog.text
    assert agents == ["AgentA"]


def test_setup_agent_data_invalid_type_raises():
    with pytest.raises(ValueError):
        _setup_agent_data("not valid", agent_selection=False, agents=None)  # type: ignore


def test_setup_agent_data_skips_non_adp_items_in_list(caplog):
    adp = make_agent_data_point(agent_name="AgentA")
    with caplog.at_level("WARNING"):
        data_dict, agents = _setup_agent_data(
            [adp, "not_an_adp"],  # type: ignore
            agent_selection=False,
            agents=None,
        )
    assert len(data_dict["AgentA"]) == 1
    assert "AgentA" in agents


def test_setup_agent_data_agent_selection_single_agent_no_prompt():
    """With a single agent, agent_selection=True should not prompt."""
    adp = make_agent_data_point(agent_name="AgentA")
    data_dict, agents = _setup_agent_data(adp, agent_selection=True, agents=None)
    assert agents == ["AgentA"]


def test_setup_agent_data_agent_selection_with_explicit_agents_skips_prompt():
    """agents= overrides agent_selection, no prompt even with multiple agents."""
    adp_a = make_agent_data_point(agent_name="AgentA")
    adp_b = make_agent_data_point(agent_name="AgentB")
    data_dict, agents = _setup_agent_data(
        [adp_a, adp_b], agent_selection=True, agents=["AgentA"]
    )
    assert agents == ["AgentA"]


# ── evaluate ──────────────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def mock_save():
    """Prevent evaluate() from actually writing to disk."""
    with patch("railtracks.evaluations.runners._evaluate.save") as m:
        yield m


def test_evaluate_single_adp_returns_one_result(mock_save):
    adp = make_agent_data_point(agent_name="AgentA")
    ev = make_evaluator()
    results = evaluate(adp, [ev], agent_selection=False)
    assert len(results) == 1


def test_evaluate_calls_evaluator_run(mock_save):
    adp = make_agent_data_point(agent_name="AgentA")
    ev = make_evaluator()
    evaluate(adp, [ev], agent_selection=False)
    ev.run.assert_called_once()


def test_evaluate_result_agent_name(mock_save):
    adp = make_agent_data_point(agent_name="AgentA")
    ev = make_evaluator()
    results = evaluate(adp, [ev], agent_selection=False)
    assert results[0].agents[0]["agent_name"] == "AgentA"


def test_evaluate_result_evaluation_name(mock_save):
    adp = make_agent_data_point(agent_name="AgentA")
    ev = make_evaluator()
    results = evaluate(adp, [ev], agent_selection=False, name="My Run")
    assert results[0].evaluation_name == "My Run"


def test_evaluate_multiple_agents_returns_multiple_results(mock_save):
    adp_a = make_agent_data_point(agent_name="AgentA")
    adp_b = make_agent_data_point(agent_name="AgentB")
    ev = make_evaluator()
    results = evaluate([adp_a, adp_b], [ev], agent_selection=False)
    assert len(results) == 2


def test_evaluate_agents_filter_limits_results(mock_save):
    adp_a = make_agent_data_point(agent_name="AgentA")
    adp_b = make_agent_data_point(agent_name="AgentB")
    ev = make_evaluator()
    results = evaluate([adp_a, adp_b], [ev], agent_selection=False, agents=["AgentA"])
    assert len(results) == 1
    assert results[0].agents[0]["agent_name"] == "AgentA"


def test_evaluate_evaluator_failure_skips_result(mock_save):
    adp = make_agent_data_point(agent_name="AgentA")
    ev = make_evaluator()
    ev.run.side_effect = RuntimeError("oops")
    results = evaluate(adp, [ev], agent_selection=False)
    # Still returns an EvaluationResult, but with no evaluator results
    assert len(results) == 1
    assert results[0].evaluator_results == []


def test_evaluate_payload_callback_called(mock_save):
    adp = make_agent_data_point(agent_name="AgentA")
    ev = make_evaluator()
    callback = MagicMock()
    evaluate(adp, [ev], agent_selection=False, payload_callback=callback)
    callback.assert_called_once()


def test_evaluate_payload_callback_receives_dict(mock_save):
    adp = make_agent_data_point(agent_name="AgentA")
    ev = make_evaluator()
    received = []
    evaluate(adp, [ev], agent_selection=False, payload_callback=received.append)
    assert len(received) == 1
    assert isinstance(received[0], dict)


def test_evaluate_calls_save(mock_save):
    adp = make_agent_data_point(agent_name="AgentA")
    ev = make_evaluator()
    evaluate(adp, [ev], agent_selection=False)
    mock_save.assert_called_once()


def test_evaluate_no_evaluators(mock_save):
    adp = make_agent_data_point(agent_name="AgentA")
    results = evaluate(adp, [], agent_selection=False)
    assert len(results) == 1
    assert results[0].evaluator_results == []


def test_evaluate_invalid_data_raises(mock_save):
    ev = make_evaluator()
    with pytest.raises(ValueError):
        evaluate("invalid", [ev], agent_selection=False)  # type: ignore
