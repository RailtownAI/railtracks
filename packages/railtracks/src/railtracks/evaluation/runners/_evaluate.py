from collections import defaultdict
from ..data.evaluation_dataset import EvaluationDataset
from ..evaluators import Evaluator
from ...utils.point import AgentDataPoint

from ...utils.logging.create import get_rt_logger
from ..result import EvaluationResult
from ..utils import save_evaluation_results

logger = get_rt_logger("evaluate")


def evaluate(
    data: AgentDataPoint | list[AgentDataPoint] | EvaluationDataset,
    evaluators: list[Evaluator],
):
    evaluator_results = {}
    data_dict: dict[str, list[AgentDataPoint]] = defaultdict(list)

    if isinstance(data, EvaluationDataset):
        data_dict = data.data_points_dict
    elif isinstance(data, list):
        for dp in data:
            if not isinstance(dp, AgentDataPoint):
                logger.warning(
                    "All items in the data list must be AgentDataPoint instances."
                )
                continue
            data_dict[dp.agent_name].append(dp)

    elif isinstance(data, AgentDataPoint):
        data_dict[data.agent_name].append(data)
    else:
        raise ValueError(
            "Data must be an EvaluationDataset, a list of AgentDataPoint instances, or a single AgentDataPoint."
        )

    for agent in data_dict:
        
        logger.info(
            f"Evaluating agent: {agent} with {len(data_dict[agent])} data points."
        )

        for evaluator in evaluators:
            logger.info(
                f"Running evaluator: {evaluator.__class__.__name__}({str(evaluator.id)[:4]}...)"
            )
            result = evaluator.run(data_dict[agent])
            evaluator_results[(agent, evaluator.id)] = result
            logger.info(
                f"Completed evaluator: {evaluator.__class__.__name__}({str(evaluator.id)[:4]}...)"
            )

    try:
        logger.info("Evaluation run complete.")
        save_evaluation_results(list(evaluator_results.values()))
    except Exception as e:
        logger.error(f"Failed to save evaluation results: {e}")
    return evaluator_results
