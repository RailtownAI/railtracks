import railtracks as rt

from .evaluator import Evaluator
from ..data import Dataset
from ...utils.point import AgentDataPoint
from .metrics import Numerical

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
        self.metrics: list[Numerical] = []

    def run(self, data: AgentDataPoint | list[AgentDataPoint] | Dataset):
        if isinstance(data, AgentDataPoint):
            data = [data]
        elif isinstance(data, Dataset):
            return

        self._retrieve_tool_stats(data)

    def _retrieve_tool_stats(self, data: list[AgentDataPoint]):
        """Retrieve tool usage statistics from the agent data points.

        Args:
            data: A list of AgentDataPoint instances.
        """
        stats = {}
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
                        stats[tool_name]["failure_count"] += 1

        for tool_name, tool_data in stats.items():
            failure_rate = (
                tool_data["failure_count"] / tool_data["usage_count"]
                if tool_data["usage_count"] > 0
                else 0.0
            )
            self.metrics.append(
                ToolFailureRate(
                    name=f"{tool_name}_failure_rate",
                    value=failure_rate,
                )
            )
            self.metrics.append(
                ToolFrequency(
                    name=f"{tool_name}_usage_frequency",
                    value=tool_data["usage_count"],
                )
            )
