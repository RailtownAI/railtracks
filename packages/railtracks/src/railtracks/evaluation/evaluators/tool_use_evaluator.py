from collections import defaultdict
from typing import TypedDict
from uuid import UUID

from ...utils.logging.create import get_rt_logger
from ..point import AgentDataPoint, Status
from ..result import (
    EvaluatorResult,
    ToolAggregateResult,
    ToolMetricResult,
)
from .evaluator import Evaluator
from .metrics import ToolMetric
from enum import Enum

logger = get_rt_logger("ToolUseEvaluator")


class ToolStats(TypedDict):
    usage_count: int
    failure_count: int
    runtimes: list[float]


METRICS = {
    "ToolFailure": ToolMetric(
        name="ToolFailure",
        min_value=0,
        max_value=1,
    ),
    "Runtime": ToolMetric(
        name="Runtime",
        min_value=0.0,
    ),
    "FailureRate": ToolMetric(
        name="FailureRate",
        min_value=0.0,
        max_value=1.0,
    ),
    "UsageCount": ToolMetric(
        name="UsageCount",
        min_value=0,
    ),
}


class ToolUseEvaluator(Evaluator):
    def __init__(
        self,
    ):
        super().__init__()

    def run(
        self, data: list[AgentDataPoint]
    ) -> EvaluatorResult[ToolMetric, ToolMetricResult, ToolAggregateResult]:

        agent_data_ids: set[UUID] = {adp.identifier for adp in data}
        results = self._extract_tool_stats(data)
        aggregate_results = self._aggregate_stats_across_run(results)+self._aggregate_metrics(results, len(agent_data_ids))
        metrics = list(results.keys())

        return EvaluatorResult(
            evaluator_name=self.name,
            evaluator_id=self.identifier,
            agent_data_ids=agent_data_ids,
            metrics=metrics,
            metric_results=[item for sublist in results.values() for item in sublist],
            aggregate_results=aggregate_results,
        )

    def _extract_tool_stats(
        self, data: list[AgentDataPoint]
    ) -> dict[ToolMetric, list[ToolMetricResult]]:
        """
        Retrieve tool usage statistics from the agent data points.
        There is no aggregation at this level, so results are at the tool call level.

        Args:
            data: A list of AgentDataPoint instances.
        """

        results: dict[ToolMetric, list[ToolMetricResult]] = defaultdict(list)
        # (agent_datapoint_id, tool_name): stats_dict
        stats: dict[tuple[UUID, str], ToolStats] = defaultdict(
            lambda: {"usage_count": 0, "failure_count": 0, "runtimes": []}
        )

        for datapoint in data:

            for tool in datapoint.tool_details.calls:
                tool_name = tool.name
                key = (datapoint.identifier, tool_name)

                stats[key]["usage_count"] += 1

                results[METRICS["ToolFailure"]].append(
                    ToolMetricResult(
                        result_name=f"{METRICS['ToolFailure'].name}/{tool_name}",
                        agent_data_id=[datapoint.identifier],
                        metric_id=METRICS["ToolFailure"].identifier,
                        tool_name=tool_name,
                        tool_node_id=tool.identifier,
                        value=1 if tool.status == Status.FAILED else 0,
                    )
                )
                if tool.status == Status.FAILED:
                    stats[key]["failure_count"] += 1
                runtime = tool.runtime
                if runtime is not None:
                    stats[key]["runtimes"].append(runtime)

                    results[METRICS["Runtime"]].append(
                        ToolMetricResult(
                            result_name=f"{METRICS['Runtime'].name}/{tool_name}",
                            agent_data_id=[datapoint.identifier],
                            metric_id=METRICS["Runtime"].identifier,
                            tool_name=tool_name,
                            tool_node_id=tool.identifier,
                            value=runtime,
                        )
                    )
        for key, tool_data in stats.items():

            adp_id, tool_name = key

            failure_rate = (
                tool_data["failure_count"] / tool_data["usage_count"]
                if tool_data["usage_count"] > 0
                else 0.0
            )
            results[METRICS["FailureRate"]].append(
                ToolMetricResult(
                    result_name=f"{METRICS['FailureRate'].name}/{tool_name}",
                    agent_data_id=[adp_id],
                    metric_id=METRICS["FailureRate"].identifier,
                    tool_name=tool_name,
                    tool_node_id=None,
                    value=failure_rate,
                )
            )

            results[METRICS["UsageCount"]].append(
                ToolMetricResult(
                    result_name=f"{METRICS['UsageCount'].name}/{tool_name}",
                    agent_data_id=[adp_id],
                    metric_id=METRICS["UsageCount"].identifier,
                    tool_name=tool_name,
                    tool_node_id=None,
                    value=tool_data["usage_count"],
                )
            )
        return results

    def _aggregate_stats_across_run(
        self, results: dict[ToolMetric, list[ToolMetricResult]]
    ) -> list[ToolAggregateResult]:
        """
        Aggregates tool usage statistics across a run. This is a separate step from the initial extraction to allow for more flexible aggregation strategies in the future.

        Args:
            results: A dictionary of ToolMetric to list of ToolMetricResult at the tool call level.
        Returns:
            A list of ToolAggregateResult instances containing the aggregated results at the run level.
        """
        aggregates: list[ToolAggregateResult] = []

        metric_results = results[METRICS["Runtime"]]
        metric_results_by_adp_id: dict[UUID, list[ToolMetricResult]] = defaultdict(
            list
        )

        values: dict[UUID, dict[str, list[tuple[UUID|None, float | int]]]] = defaultdict(dict)

        for result in metric_results:
            for adp_id in result.agent_data_id:
                metric_results_by_adp_id[adp_id].append(result)

        for adp_id in metric_results_by_adp_id:
            values[adp_id] = defaultdict(list)

            for tmr in metric_results_by_adp_id[adp_id]:
                values[adp_id][tmr.tool_name].append((tmr.tool_node_id, tmr.value))

            for tool_name, vals in values[adp_id].items():
                aggregate_result = ToolAggregateResult(
                    metric=METRICS["Runtime"],
                    values=[v[1] for v in vals],
                    tool_name=tool_name,
                    tool_node_ids={adp_id: [v[0] for v in vals]}, # type: ignore[assignment] this is hacky..
                )
                aggregates.append(aggregate_result)
        return aggregates

    def _aggregate_metrics(
        self, results: dict[ToolMetric, list[ToolMetricResult]], num_data_points: int
    ) -> list[ToolAggregateResult]:
        """Aggregates the ToolUseEvaluator metrics on an agent level."""

        aggregates: list[ToolAggregateResult] = []
        # for metric in [METRICS["FailureRate"], METRICS["UsageCount"]]:
        for metric in results:

            metric_results = results[metric]
            values: dict[str, list[float | int]] = defaultdict(list)
            for tmr in metric_results:
                values[tmr.tool_name].append(tmr.value)

            for tool_name, vals in values.items():

                if metric == METRICS["UsageCount"]:
                    length = len(values[tool_name])

                    # We need to add 0s to UsageCount for AgentDataPoints
                    # That did not invoke this particular tool
                    for _ in range(num_data_points-length):
                        values[tool_name].append(0) 
                
                aggregate_result = ToolAggregateResult(
                    metric=metric, 
                    values=vals, 
                    tool_name=tool_name,
                )
                aggregates.append(aggregate_result)

        return aggregates
