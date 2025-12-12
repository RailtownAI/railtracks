import railtracks as rt

from .evaluator import Evaluator
from ..data import Dataset
from ...utils.point import AgentDataPoint
from .metrics import Metric

class ToolMetric(Metric):
    """A Metric to evaluate tool use in agent outputs."""
    frequency: int
    failture_rate: float

class ToolUseEvaluator(Evaluator):
    def __init__(self, 
    ):
        super().__init__()

    def run(self, data: AgentDataPoint | list[AgentDataPoint] | Dataset):
        pass


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
        return stats              
