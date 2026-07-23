import pytest
from railtracks.evaluations import RuntimeEvaluator
from railtracks.evaluations.result import MetricResult, NumericalAggregateNode

from .conftest import make_agent_data_point


def test_run_records_runtime_for_each_agent_invocation():
    data = [
        make_agent_data_point(runtime=1.25),
        make_agent_data_point(runtime=2.75),
    ]

    result = RuntimeEvaluator().run(data)

    assert {metric.name for metric in result.metrics} == {"Runtime"}
    assert [metric_result.value for metric_result in result.metric_results] == [
        1.25,
        2.75,
    ]
    assert all(
        isinstance(metric_result, MetricResult)
        for metric_result in result.metric_results
    )


def test_run_skips_invocations_without_runtime():
    measured = make_agent_data_point(runtime=1.5)
    missing = make_agent_data_point(runtime=None)

    result = RuntimeEvaluator().run([measured, missing])

    assert [metric_result.value for metric_result in result.metric_results] == [1.5]
    assert result.agent_data_ids == {measured.identifier, missing.identifier}


def test_run_without_measured_invocations_returns_empty_results():
    result = RuntimeEvaluator().run([make_agent_data_point(runtime=None)])

    assert result.metrics == []
    assert result.metric_results == []
    assert result.aggregate_results.roots == []


def test_run_aggregates_and_serializes_for_the_visualizer():
    result = RuntimeEvaluator().run(
        [
            make_agent_data_point(runtime=1.0),
            make_agent_data_point(runtime=3.0),
        ]
    )

    assert len(result.aggregate_results.roots) == 1
    aggregate = result.aggregate_results.get(result.aggregate_results.roots[0])
    assert isinstance(aggregate, NumericalAggregateNode)
    assert aggregate.mean == pytest.approx(2.0)
    assert aggregate.minimum == pytest.approx(1.0)
    assert aggregate.maximum == pytest.approx(3.0)

    serialized = result.model_dump(mode="json")
    assert serialized["evaluator_name"] == "RuntimeEvaluator"
    assert serialized["metric_results"][0]["type"] == "Base"
    assert {
        node["type"] for node in serialized["aggregate_results"]["nodes"].values()
    } == {"Base", "NumericalAggregate"}
