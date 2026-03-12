from datetime import datetime, timezone
from uuid import UUID, uuid4

from railtracks.evaluations.evaluators.metrics import Numerical
from railtracks.evaluations.result.aggregate_results import (
    AggregateForest,
    NumericalAggregateNode,
)
from railtracks.evaluations.result.evaluator_results import (
    EvaluationResult,
    EvaluatorResult,
)
from railtracks.evaluations.result.metric_results import MetricResult

# ── Helpers ───────────────────────────────────────────────────────────────────


def make_evaluation_result(name: str | None = None) -> EvaluationResult:
    return EvaluationResult(
        created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        completed_at=datetime(2026, 1, 1, 0, 0, 5, tzinfo=timezone.utc),
        evaluation_name=name,
        agents=[
            {
                "agent_name": "AgentA",
                "agent_node_ids": [
                    {"session_id": uuid4(), "agent_node_id": uuid4()}
                ],
            }
        ],
        metrics_map={},
        evaluator_results=[],
    )


def make_evaluator_result() -> EvaluatorResult:
    forest = AggregateForest[NumericalAggregateNode, MetricResult]()
    return EvaluatorResult(
        evaluator_name="TestEvaluator",
        evaluator_id="test-id-123",
        aggregate_results=forest,
    )


# ── EvaluatorResult ───────────────────────────────────────────────────────────


def test_evaluator_result_stores_name_and_id():
    er = make_evaluator_result()
    assert er.evaluator_name == "TestEvaluator"
    assert er.evaluator_id == "test-id-123"


def test_evaluator_result_default_empty_metric_results():
    er = make_evaluator_result()
    assert er.metric_results == []


def test_evaluator_result_default_empty_agent_data_ids():
    er = make_evaluator_result()
    assert er.agent_data_ids == set()


def test_evaluator_result_with_metric_results():
    mr = MetricResult(result_name="r", metric_id="m", agent_data_id=[uuid4()], value=1.0)
    forest = AggregateForest[NumericalAggregateNode, MetricResult]()
    er = EvaluatorResult(
        evaluator_name="E",
        evaluator_id="id",
        metric_results=[mr],
        aggregate_results=forest,
    )
    assert len(er.metric_results) == 1
    assert er.metric_results[0] is mr


def test_evaluator_result_with_agent_data_ids():
    adp_id = uuid4()
    forest = AggregateForest[NumericalAggregateNode, MetricResult]()
    er = EvaluatorResult(
        evaluator_name="E",
        evaluator_id="id",
        agent_data_ids={adp_id},
        aggregate_results=forest,
    )
    assert adp_id in er.agent_data_ids


def test_evaluator_result_with_metrics():
    metric = Numerical(name="Latency")
    forest = AggregateForest[NumericalAggregateNode, MetricResult]()
    er = EvaluatorResult(
        evaluator_name="E",
        evaluator_id="id",
        metrics=[metric],
        aggregate_results=forest,
    )
    assert len(er.metrics) == 1
    assert er.metrics[0] == metric


# ── EvaluationResult ──────────────────────────────────────────────────────────


def test_evaluation_result_has_uuid():
    er = make_evaluation_result()
    assert isinstance(er.evaluation_id, UUID)


def test_evaluation_result_unique_ids():
    er1 = make_evaluation_result()
    er2 = make_evaluation_result()
    assert er1.evaluation_id != er2.evaluation_id


def test_evaluation_result_stores_name():
    er = make_evaluation_result(name="My Evaluation")
    assert er.evaluation_name == "My Evaluation"


def test_evaluation_result_name_defaults_to_none():
    er = make_evaluation_result()
    assert er.evaluation_name is None


def test_evaluation_result_stores_timestamps():
    created = datetime(2026, 1, 1, tzinfo=timezone.utc)
    completed = datetime(2026, 1, 1, 0, 0, 10, tzinfo=timezone.utc)
    er = EvaluationResult(
        created_at=created,
        completed_at=completed,
        agents=[],
        metrics_map={},
        evaluator_results=[],
    )
    assert er.created_at == created
    assert er.completed_at == completed


def test_evaluation_result_stores_agents():
    agent_entry = {
        "agent_name": "Bot",
        "agent_node_ids": [{"session_id": uuid4(), "agent_node_id": uuid4()}],
    }
    er = EvaluationResult(
        created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        completed_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        agents=[agent_entry],
        metrics_map={},
        evaluator_results=[],
    )
    assert len(er.agents) == 1
    assert er.agents[0]["agent_name"] == "Bot"


def test_evaluation_result_stores_metrics_map():
    metric = Numerical(name="Latency")
    er = EvaluationResult(
        created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        completed_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        agents=[],
        metrics_map={metric.identifier: metric},
        evaluator_results=[],
    )
    assert metric.identifier in er.metrics_map


def test_evaluation_result_stores_evaluator_results():
    ev_result = make_evaluator_result()
    er = EvaluationResult(
        created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        completed_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        agents=[],
        metrics_map={},
        evaluator_results=[ev_result],
    )
    assert len(er.evaluator_results) == 1
    assert er.evaluator_results[0] is ev_result
