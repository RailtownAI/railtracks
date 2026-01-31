from uuid import UUID
from collections import defaultdict
from .evaluator import Evaluator
from ...utils.point import AgentDataPoint
from .metrics import ToolMetric
from ..result import EvaluatorResult, MetricResult, AggregateNumericalResult, ToolMetricResult

from ...utils.logging.create import get_rt_logger
from typing import TypedDict

logger = get_rt_logger("ToolUseEvaluator")

class ToolStats(TypedDict):
    usage_count: int
    failure_count: int
    latencies: list[float]

class ToolUseEvaluator(Evaluator):
    def __init__(
        self,
    ):
        super().__init__()

    def run(self, data: list[AgentDataPoint]) -> EvaluatorResult:

        agent_data_ids: set[UUID] = {adp.id for adp in data}
        results = self._retrieve_tool_stats(data)
        aggregate_results = self._aggregate_metrics(results)
        metrics = list(results.keys())

        return EvaluatorResult(
            evaluator_name=self.name,
            evaluator_id=self.identifier,
            agent_data_ids=agent_data_ids,
            metrics=metrics,
            results= [item for sublist in results.values() for item in sublist] + aggregate_results,
        )

    def _retrieve_tool_stats(
        self, data: list[AgentDataPoint]
    ) -> dict[ToolMetric, list[ToolMetricResult]]:
        """Retrieve tool usage statistics from the agent data points.

        Args:
            data: A list of AgentDataPoint instances.
        """

        results: dict[ToolMetric, list[ToolMetricResult]] = defaultdict(list)
        # (agent_datapoint_id, tool_name): stats_dict
        stats: dict[tuple[str, str], ToolStats] = defaultdict(lambda: {"usage_count": 0, "failure_count": 0, "latencies": []})
        for datapoint in data:
            if datapoint.agent_internals is not None:
                for tool in datapoint.agent_internals.get("tool_invocations", []):

                    tool_name = tool.get("name")
                    key = (str(datapoint.id), tool_name)
                    
                    stats[key]["usage_count"] += 1
                    if "There was an error running the tool" in tool["result"]:
                        stats[key]["failure_count"] += 1  # TODO: Add a ticket for better way of handling this
                    
                    # Track individual latency if available
                    runtime = tool.get("runtime")
                    if runtime is not None:
                        
                        metric_name = "Latency"
                        stats[key]["latencies"].append(runtime)

                        tool_latency_metric = ToolMetric(
                            name="Latency",
                            min_value=0.0,
                        )
                        results[tool_latency_metric].append(
                                ToolMetricResult(
                                    result_name=f"{metric_name}/{tool_name}",
                                    agent_data_id=[datapoint.id],
                                    metric_id=tool_latency_metric.identifier,
                                    tool_name=tool_name,
                                    tool_call_id=tool.get("id", None),
                                    value=runtime,
                                )
                            )
            else:
                logger.warning(
                    f"AgentDataPoint for agent {datapoint.agent_name} is missing internals; skipping tool usage stats."
                )
                continue

        for key, tool_data in stats.items():

            adp_id, tool_name = key
            
            metric_name = f"LatencyAcrossRun"
            tool_latency_metric = ToolMetric(
                name=metric_name,
                min_value=0.0,
            )
            avg_latency = (
                sum(tool_data["latencies"]) / len(tool_data["latencies"])
                if tool_data["latencies"]
                else 0.0
            )
            results[tool_latency_metric].append(
                ToolMetricResult(
                    result_name=f"{metric_name}/{tool_name}",
                    agent_data_id=[UUID(adp_id)],
                    metric_id=tool_latency_metric.identifier,
                    tool_name=tool_name,
                    tool_call_id=None,
                    value=avg_latency,
                )
            )
            
            metric_name = f"FailureRate"
            tool_failure_metric = ToolMetric(
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
                ToolMetricResult(
                    result_name=f"{metric_name}/{tool_name}",
                    agent_data_id=[UUID(adp_id)],
                    metric_id=tool_failure_metric.identifier,
                    tool_name=tool_name,
                    tool_call_id=None,
                    value=failure_rate,
                )
            )

            metric_name = f"UsageCount"
            tool_frequency_metric = ToolMetric(
                name=metric_name,
                min_value=0,
            )
            results[tool_frequency_metric].append(
                ToolMetricResult(
                    result_name=f"{metric_name}/{tool_name}",
                    agent_data_id=[UUID(adp_id)],
                    metric_id=tool_frequency_metric.identifier,
                    tool_name=tool_name,
                    tool_call_id=None,
                    value=tool_data["usage_count"],
                )
                )

        return results

    def _aggregate_metrics(
        self, results: dict[ToolMetric, list[ToolMetricResult]]
    ) -> list[AggregateNumericalResult]:
        """Aggregates the ToolUseEvaluator metrics on an agent level."""

        aggregates = []
        for metric in results:

            metric_results = results[metric]

            values = [tmr.value for tmr in metric_results]


            aggregate_result = AggregateNumericalResult(
                metric=metric,
                values=values,
            )
            aggregates.append(aggregate_result)

        return aggregates
