import railtracks as rt
from collections import defaultdict
from .evaluator import Evaluator
from ..data import EvaluationDataset
from ...utils.point import AgentDataPoint
from .metrics import Numerical, Metric
from ..result import EvaluatorResult, MetricResult, AggregateNumericalResult

from ...utils.logging.create import get_rt_logger
from uuid import UUID

logger = get_rt_logger("ToolUseEvaluator")


class ToolFrequency(Numerical):
    min_value: int | float | None = 0


class ToolFailureRate(Numerical):
    min_value: float | int | None = 0.0
    max_value: float | int | None = 1.0


class ToolUseEvaluator(Evaluator):
    def __init__(
        self,
    ):
        super().__init__()

        self.results: dict[Numerical, list[tuple[str, MetricResult]]] = defaultdict(
            list
        )

    def run(self, data: list[AgentDataPoint]) -> EvaluatorResult:
        if isinstance(data, AgentDataPoint):
            data = [data]
        elif isinstance(data, EvaluationDataset):
            data = data.data_points_list

        self.agent_name = data[0].agent_name

        self._retrieve_tool_stats(data)
        self.aggregate_results = self._aggregate_metrics()



        self._result = EvaluatorResult(
            agent_name=self.agent_name,
            evaluator_name=self.name,
            evaluator_id=self._id,
            metrics=self.metrics,
            results=[], # What do we want here?
            # results=[result for _, result in self.results] + self.aggregate_results,
        )

        return self._result

    @property
    def metrics(self) -> list[Metric]:
        return list(self.results.keys())

    def _retrieve_tool_stats(self, data: list[AgentDataPoint]):
        """Retrieve tool usage statistics from the agent data points.

        Args:
            data: A list of AgentDataPoint instances.
        """
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
            tool_failure_metric = ToolFailureRate(
                name=metric_name,
                data_type=float,
                min_value=0.0,
                max_value=1.0,
            )
            failure_rate = (
                tool_data["failure_count"] / tool_data["usage_count"]
                if tool_data["usage_count"] > 0
                else 0.0
            )
            self.results[tool_failure_metric].append(
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
            tool_frequency_metric = ToolFrequency(
                name=metric_name,
                data_type=int,
                min_value=0,
            )
            self.results[tool_frequency_metric].append(
                (
                    adp_id,
                    MetricResult(
                        metric_name=metric_name,
                        metric_id=tool_frequency_metric.identifier,
                        value=tool_data["usage_count"],
                    ),
                )
            )

    def _aggregate_metrics(self):
        """Aggregates the ToolUseEvaluator metrics on an agent level."""

        # self.results: dict[Metric, list[tuple[str, MetricResult]]] = defaultdict(list)
        aggregates = []
        for metric in self.results:

            adp_mr = self.results[metric]

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
        # tool_metric_aggregates: dict[str, list[str | float | int]] = defaultdict(list)

        # for result in self.results:
        #     tool_metric_aggregates[str(result.metric_id)].append(result.value)
        # aggregate_results: list[AggregateNumericalResult] = []

        # for metric_id, values in tool_metric_aggregates.items():
        #     metric = self.metrics_lookup.get(metric_id)
        #     if isinstance(metric, ToolFailureRate) or isinstance(metric, ToolFrequency):
        #         aggregate = AggregateNumericalResult(
        #             metric=metric,
        #             values=[float(v) for v in values],
        #         )

        #         aggregate_results.append(aggregate)

        # return aggregate_results
