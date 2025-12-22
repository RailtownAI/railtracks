from ..data.evaluation_dataset import EvaluationDataset
from ..evaluators import Evaluator
from ...utils.point import AgentDataPoint

from ...utils.logging.create import get_rt_logger

logger = get_rt_logger("evaluate")


def evaluate(
    evaluators: list[Evaluator],
    data: AgentDataPoint | list[AgentDataPoint] | EvaluationDataset,
):
    # Step 1: Need to divide the data by agents
    agents: set[str] = set()

    if isinstance(data, EvaluationDataset):
        pass
    elif isinstance(data, list):
        for dp in data:
            if not isinstance(dp, AgentDataPoint):
                raise ValueError(
                    "All items in the data list must be AgentDataPoint instances."
                )
            agents.add(dp.agent_name)
    elif isinstance(data, AgentDataPoint):
        agents.add(data.agent_name)
    else:
        raise ValueError(
            "Data must be an EvaluationDataset, a list of AgentDataPoint instances, or a single AgentDataPoint."
        )
