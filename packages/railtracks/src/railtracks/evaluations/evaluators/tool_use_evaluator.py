from collections import defaultdict
from typing import TypedDict
from uuid import UUID

from ...utils.logging.create import get_rt_logger
from ..point import AgentDataPoint, Status
from ..result import (
    AggregateForest,
    EvaluatorResult,
    ToolAggregateNode,
    ToolMetricResult,
)
from .evaluator import Evaluator
from .metrics import ToolMetric

logger = get_rt_logger(__name__)


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
    """
    Evaluator that analyzes tool usage patterns across agent runs.

    Computes per-call and aggregated metrics for each tool, including
    runtime, failure rate, and usage count.
    """

    def __init__(
        self,
    ):
        super().__init__()

    def run(
        self, data: list[AgentDataPoint]
    ) -> EvaluatorResult[ToolMetric, ToolMetricResult, ToolAggregateNode]:
        """
        Run the evaluator over a list of agent data points.

        Args:
            data: A list of AgentDataPoint instances to evaluate.

        Returns:
            An EvaluatorResult containing per-call metric results and
            aggregated nodes across runs.
        """
        agent_data_ids: set[UUID] = {adp.identifier for adp in data}
        forest = AggregateForest[ToolAggregateNode, ToolMetricResult]()

        results = self._extract_tool_stats(data, forest)
        self._aggregate_per_run(results, forest)
        self._aggregate_across_runs(results, forest)

        metrics = list(results.keys())

        return EvaluatorResult(
            evaluator_name=self.name,
            evaluator_id=self.identifier,
            agent_data_ids=agent_data_ids,
            metrics=metrics,
            metric_results=[item for sublist in results.values() for item in sublist],
            aggregate_results=forest,
        )

    def _extract_tool_stats(
        self,
        data: list[AgentDataPoint],
        forest: AggregateForest[ToolAggregateNode, ToolMetricResult],
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

                metric_result = ToolMetricResult(
                    result_name=f"{METRICS['Runtime'].name}/{tool_name}",
                    agent_data_id=[datapoint.identifier],
                    metric_id=METRICS["Runtime"].identifier,
                    tool_name=tool_name,
                    tool_node_id=tool.identifier,
                    value=tool.runtime if tool.runtime is not None else 0.0,
                )
                forest.add_node(metric_result)
                results[METRICS["ToolFailure"]].append(metric_result)

                if tool.status == Status.FAILED:
                    stats[key]["failure_count"] += 1
                runtime = tool.runtime

                if runtime is not None:
                    stats[key]["runtimes"].append(runtime)

                    metric_result = ToolMetricResult(
                        result_name=f"{METRICS['Runtime'].name}/{tool_name}",
                        agent_data_id=[datapoint.identifier],
                        metric_id=METRICS["Runtime"].identifier,
                        tool_name=tool_name,
                        tool_node_id=tool.identifier,
                        value=runtime,
                    )
                    forest.add_node(metric_result)
                    results[METRICS["Runtime"]].append(metric_result)

        for key, tool_data in stats.items():
            adp_id, tool_name = key

            failure_rate = (
                tool_data["failure_count"] / tool_data["usage_count"]
                if tool_data["usage_count"] > 0
                else 0.0
            )

            tmr = ToolMetricResult(
                result_name=f"{METRICS['FailureRate'].name}/{tool_name}",
                agent_data_id=[adp_id],
                metric_id=METRICS["FailureRate"].identifier,
                tool_name=tool_name,
                tool_node_id=None,
                value=failure_rate,
            )
            forest.add_node(tmr)
            results[METRICS["FailureRate"]].append(tmr)

            tmr = ToolMetricResult(
                result_name=f"{METRICS['UsageCount'].name}/{tool_name}",
                agent_data_id=[adp_id],
                metric_id=METRICS["UsageCount"].identifier,
                tool_name=tool_name,
                tool_node_id=None,
                value=tool_data["usage_count"],
            )
            forest.add_node(tmr)
            results[METRICS["UsageCount"]].append(tmr)

        return results

    def _aggregate_per_run(
        self,
        results: dict[ToolMetric, list[ToolMetricResult]],
        forest: AggregateForest[ToolAggregateNode, ToolMetricResult],
    ) -> None:
        metric_results = results[METRICS["Runtime"]]
        metric_results_by_adp_id: dict[UUID, list[ToolMetricResult]] = defaultdict(list)

        values: dict[UUID, dict[str, list[ToolMetricResult]]] = defaultdict(dict)

        for result in metric_results:
            for adp_id in result.agent_data_id:
                metric_results_by_adp_id[adp_id].append(result)

        for adp_id in metric_results_by_adp_id:
            values[adp_id] = defaultdict(list)

            for tmr in metric_results_by_adp_id[adp_id]:
                values[adp_id][tmr.tool_name].append(tmr)

            for tool_name in values[adp_id]:
                aggregate_node = ToolAggregateNode(
                    name=f"Aggregate/{METRICS['Runtime'].name}",
                    metric=METRICS["Runtime"],
                    tool_name=tool_name,
                    children=[tmr.identifier for tmr in values[adp_id][tool_name]],
                    forest=forest,
                )
                forest.roots.append(aggregate_node.identifier)
                forest.add_node(aggregate_node)

    def _aggregate_across_runs(
        self,
        results: dict[ToolMetric, list[ToolMetricResult]],
        forest: AggregateForest[ToolAggregateNode, ToolMetricResult],
    ) -> None:
        """
        Aggregates the ToolUseEvaluator metrics across runs on an agent level.
        This is a separate step from the initial extraction to allow for more flexible aggregation strategies in the future.

        Args:
            results: A dictionary of ToolMetric to list of ToolMetricResult at the tool call level.

        Returns:
            A list of ToolAggregateNode instances containing the aggregated results at the run level.
        """

        for metric in [METRICS["FailureRate"], METRICS["UsageCount"]]:
            metric_results = results[metric]
            values: dict[str, list[ToolMetricResult]] = defaultdict(list)

            for tmr in metric_results:
                values[tmr.tool_name].append(tmr)

            for tool_name, vals in values.items():
                aggregate_node = ToolAggregateNode(
                    name=f"Aggregate/{metric.name}",
                    metric=metric,
                    tool_name=tool_name,
                    children=[val.identifier for val in vals],
                    forest=forest,
                )
                forest.roots.append(aggregate_node.identifier)
                forest.add_node(aggregate_node)

        ## Aggregation of Runtime ------------------------------
        tool_breakdown = defaultdict(list)
        for root_id in forest.roots:
            agg = forest.get(root_id)
            if isinstance(agg, ToolMetricResult):
                raise ValueError(
                    f"Expected root nodes in the forest to be ToolAggregateNodes, but got {type(agg)}"
                )
            if agg.metric == METRICS["Runtime"]:
                tool_breakdown[agg.tool_name].append(agg)

        for tool_name in tool_breakdown:
            if len(tool_breakdown[tool_name]) < 2:
                raise ValueError(
                    f"Expected multiple aggregate nodes for tool '{tool_name}' to perform cross-run aggregation, but found only one. Found nodes: {[agg.identifier for agg in tool_breakdown[tool_name]]}"
                )
            parent = ToolAggregateNode(
                name=f"Aggregate/{METRICS['Runtime'].name}",
                metric=METRICS["Runtime"],
                tool_name=tool_name,
                children=[
                    tool_agg.identifier for tool_agg in tool_breakdown[tool_name]
                ],
                forest=forest,
            )
            forest.add_node(parent)
            forest.roots.append(parent.identifier)
