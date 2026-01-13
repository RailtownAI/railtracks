import railtracks as rt
from collections import defaultdict
from .evaluator import Evaluator
from ..data import EvaluationDataset
from ...utils.point import AgentDataPoint
from .metrics import Numerical, Metric
from ..result import EvaluatorResult, MetricResult

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
        self.metrics: list[Metric] = []
        self.results: list[MetricResult] = []

    def run(self, data: list[AgentDataPoint]) -> EvaluatorResult:
        if isinstance(data, AgentDataPoint):
            data = [data]
        elif isinstance(data, EvaluationDataset):
            data = data.data_points_list

        self.agent_name = data[0].agent_name

        self._retrieve_tool_stats(data)
        self._result = EvaluatorResult(
            agent_name=self.agent_name,
            evaluator_name=self.__class__.__name__,
            evaluator_id=self._id,
            metrics=self.metrics,
            results=self.results,
        )

        return self._result

    def _retrieve_tool_stats(self, data: list[AgentDataPoint]):
        """Retrieve tool usage statistics from the agent data points.

        Args:
            data: A list of AgentDataPoint instances.
        """
        stats: dict[str, dict[str, int]] = {}

        for datapoint in data:
            if datapoint.agent_internals is not None:
                for tool in datapoint.agent_internals.get("tool_invocations", []):
                    tool_name = tool.get("name")
                    if tool_name not in stats:
                        stats[tool_name] = {
                            "usage_count": 0,
                            "failure_count": 0,
                        }
                    stats[tool_name]["usage_count"] += 1
                    if "Exception message" in tool["result"]:
                        stats[tool_name][
                            "failure_count"
                        ] += 1  # TODO: Add a ticket for better way of handling this
            else:
                logger.warning(
                    f"AgentDataPoint for agent {datapoint.agent_name} is missing internals; skipping tool usage stats."
                )
                continue

        for tool_name, tool_data in stats.items():
            failure_rate = (
                tool_data["failure_count"] / tool_data["usage_count"]
                if tool_data["usage_count"] > 0
                else 0.0
            )

            # ToolFailureRate metric
            metric = ToolFailureRate(
                name=f"({tool_name})_failure_rate",
                min_value=0.0,
                max_value=1.0,
            )
            self.metrics.append(metric)
            metric_result = MetricResult(
                metric_name=f"({tool_name})_failure_rate",
                metric_id=UUID(metric.identifier),
                value=failure_rate,
            )
            self.results.append(metric_result)

            # ToolFrequency metric
            metric = ToolFrequency(
                name=f"({tool_name})_usage_count",
                min_value=0,
            )
            metric_result = MetricResult(
                metric_name=f"({tool_name})_usage_count",
                metric_id=UUID(metric.identifier),
                value=tool_data["usage_count"],
            )
            self.metrics.append(metric)

            self.results.append(metric_result)
