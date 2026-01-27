from uuid import UUID
from collections import defaultdict
from .evaluator import Evaluator
from ..data import EvaluationDataset
from ...utils.point import AgentDataPoint
from .metrics import Numerical, Metric
from ..result import EvaluatorResult, MetricResult, AggregateNumericalResult

from ...utils.logging.create import get_rt_logger

logger = get_rt_logger("ToolUseEvaluator")


# class ToolFrequency(Numerical):
#     min_value: int | float | None = 0


# class ToolFailureRate(Numerical):
#     min_value: float | int | None = 0.0
#     max_value: float | int | None = 1.0


class ToolUseEvaluator(Evaluator):
    def __init__(
        self,
    ):
        super().__init__()

    def run(self, data: list[AgentDataPoint]) -> EvaluatorResult:
        if isinstance(data, AgentDataPoint):
            data = [data]
        elif isinstance(data, EvaluationDataset):
            data = data.data_points_list

        agent_data_ids: set[UUID] = {adp.id for adp in data}
        results = self._retrieve_tool_stats(data)
        aggregate_results = self._aggregate_metrics(results)
        metrics = list(results.keys())

        self._result = EvaluatorResult(
            evaluator_name=self.name,
            evaluator_id=self._id,
            agent_data_ids=agent_data_ids,
            metrics=metrics,
            results=[item for sublist in results.values() for item in sublist]
            + aggregate_results,
        )

        return self._result

    def _retrieve_tool_stats(
        self, data: list[AgentDataPoint]
    ) -> dict[Numerical[int | float], list[tuple[str, MetricResult]]]:
        """Retrieve tool usage statistics from the agent data points.

        Args:
            data: A list of AgentDataPoint instances.
        """

        results: dict[Numerical, list[tuple[str, MetricResult]]] = defaultdict(list)
        # (agent_datapoint_id, tool_name): stats_dict
        stats: dict[tuple[str, str], dict[str, int]] = defaultdict(dict)

        for datapoint in data:
            if datapoint.agent_internals is not None:
                for tool in datapoint.agent_internals.get("tool_invocations", []):

                    tool_name = tool.get("name")
                    if tool_name not in stats:
                        stats[(str(datapoint.id), tool_name)] = {
                            "usage_count": 0,
                            "failure_count": 0,
                        }
                    stats[(str(datapoint.id), tool_name)]["usage_count"] += 1
                    if "There was an error running the tool" in tool["result"]:
                        stats[(str(datapoint.id), tool_name)][
                            "failure_count"
                        ] += 1  # TODO: Add a ticket for better way of handling this
            else:
                logger.warning(
                    f"AgentDataPoint for agent {datapoint.agent_name} is missing internals; skipping tool usage stats."
                )
                continue

        for key, tool_data in stats.items():

            adp_id, tool_name = key
            metric_name = f"{tool_name}(...)_failure_rate"
            tool_failure_metric = Numerical(
                name=metric_name,
                min_value=0.0,
                max_value=1.0,
            )
            failure_rate = (
                tool_data["failure_count"] / tool_data["usage_count"]
                if tool_data["usage_count"] > 0
                else 0.0
            )
            results[tool_failure_metric].append(
                (
                    adp_id,
                    MetricResult(
                        metric_name=metric_name,
                        metric_id=tool_failure_metric.identifier,
                        value=failure_rate,
                    ),
                )
            )

            metric_name = f"{tool_name}(...)_usage_count"
            tool_frequency_metric = Numerical(
                name=metric_name,
                min_value=0,
            )
            results[tool_frequency_metric].append(
                (
                    adp_id,
                    MetricResult(
                        metric_name=metric_name,
                        metric_id=tool_frequency_metric.identifier,
                        value=tool_data["usage_count"],
                    ),
                )
            )

        return results

    def _aggregate_metrics(
        self, results: dict[Numerical, list[tuple[str, MetricResult]]]
    ) -> list[AggregateNumericalResult]:
        """Aggregates the ToolUseEvaluator metrics on an agent level."""

        aggregates = []
        for metric in results:

            adp_mr = results[metric]

            values = [
                mr.value for _, mr in adp_mr if isinstance(mr.value, (int, float))
            ]

            aggregates.append(
                AggregateNumericalResult(
                    metric=metric,
                    values=values,
                )
            )

        return aggregates
