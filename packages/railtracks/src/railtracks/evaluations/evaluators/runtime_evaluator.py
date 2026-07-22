from uuid import UUID

from ..point import AgentDataPoint
from ..result import (
    AggregateForest,
    EvaluatorResult,
    MetricResult,
    NumericalAggregateNode,
)
from .evaluator import Evaluator
from .metrics import Numerical

RUNTIME_METRIC = Numerical(
    name="Runtime",
    min_value=0.0,
    description="Wall-clock runtime of an agent invocation in seconds.",
)


class RuntimeEvaluator(Evaluator):
    """Evaluate wall-clock runtime across complete agent invocations."""

    def run(
        self, data: list[AgentDataPoint]
    ) -> EvaluatorResult[Numerical, MetricResult, NumericalAggregateNode]:
        agent_data_ids: set[UUID] = {datapoint.identifier for datapoint in data}
        forest = AggregateForest[NumericalAggregateNode, MetricResult]()
        metric_results: list[MetricResult] = []

        for datapoint in data:
            if datapoint.runtime is None:
                continue

            metric_result = MetricResult(
                result_name=RUNTIME_METRIC.name,
                metric_id=RUNTIME_METRIC.identifier,
                agent_data_id=[datapoint.identifier],
                value=datapoint.runtime,
            )
            metric_results.append(metric_result)
            forest.add_node(metric_result)

        if metric_results:
            aggregate = NumericalAggregateNode(
                name=f"Aggregate/{RUNTIME_METRIC.name}",
                metric=RUNTIME_METRIC,
                children=[result.identifier for result in metric_results],
                forest=forest,
            )
            forest.add_node(aggregate)
            forest.roots.append(aggregate.identifier)

        return EvaluatorResult(
            evaluator_name=self.name,
            evaluator_id=self.identifier,
            agent_data_ids=agent_data_ids,
            metrics=[RUNTIME_METRIC] if metric_results else [],
            metric_results=metric_results,
            aggregate_results=forest,
        )
