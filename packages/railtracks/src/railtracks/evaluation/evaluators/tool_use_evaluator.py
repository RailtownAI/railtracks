import railtracks as rt
from collections import defaultdict
from .evaluator import Evaluator
from ..data import EvaluationDataset
from ...utils.point import AgentDataPoint
from .metrics import Numerical, Metric
from ..result import EvaluatorResult

from ...utils.logging.create import get_rt_logger

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
        self._metrics: dict[str, list[Metric]] = defaultdict(list)
        self._result: EvaluatorResult

    def run(
        self, data: list[AgentDataPoint]
    ) -> EvaluatorResult:
        if isinstance(data, AgentDataPoint):
            data = [data]
        elif isinstance(data, EvaluationDataset):
            data = data.data_points_list

        self._retrieve_tool_stats(data)
        self._result = EvaluatorResult(
            name=self.__class__.__name__,
            evaluator_id=self._id,
            results=self._metrics,
        )

        return self._result

    def _retrieve_tool_stats(self, data: list[AgentDataPoint]):
        """Retrieve tool usage statistics from the agent data points.

        Args:
            data: A list of AgentDataPoint instances.
        """
        stats: dict[str, dict[str, dict[str, int]]] = {}
        for datapoint in data:
            if datapoint.agent_internals is not None:
                for tool in datapoint.agent_internals.get("tool_invocations", []):
                    tool_name = tool.get("name")
                    if datapoint.agent_name not in stats:
                        stats[datapoint.agent_name] = {}
                    if tool_name not in stats[datapoint.agent_name]:
                        stats[datapoint.agent_name][tool_name] = {
                            "usage_count": 0,
                            "failure_count": 0,
                        }
                    stats[datapoint.agent_name][tool_name]["usage_count"] += 1
                    if "Exception message" in tool["result"]:
                        stats[datapoint.agent_name][tool_name]["failure_count"] += 1
            else:
                logger.warning(
                    f"AgentDataPoint for agent {datapoint.agent_name} is missing internals; skipping tool usage stats."
                )
                continue

        for agent_name, tools_data in stats.items():
            for tool_name, tool_data in tools_data.items():
                failure_rate = (
                    tool_data["failure_count"] / tool_data["usage_count"]
                    if tool_data["usage_count"] > 0
                    else 0.0
                )
                self._metrics[agent_name].append(
                    ToolFailureRate(
                        name=f"({tool_name})_failure_rate",
                        value=failure_rate,
                    )
                )
                self._metrics[agent_name].append(
                    ToolFrequency(
                        name=f"({tool_name})_usage_frequency",
                        value=tool_data["usage_count"],
                    )
                )
