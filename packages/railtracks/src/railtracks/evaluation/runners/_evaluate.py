from collections import defaultdict

from ...utils.logging.create import get_rt_logger
from ...utils.point import AgentDataPoint
from ..data.evaluation_dataset import EvaluationDataset
from ..evaluators import Evaluator
from ..result import EvaluationResult, EvaluatorResult
from ..utils import save

logger = get_rt_logger("evaluate")


def evaluate(
    data: AgentDataPoint | list[AgentDataPoint] | EvaluationDataset,
    evaluators: list[Evaluator],
    name: str | None = None,
):

    evaluator_ids: set[str] = set()

    for evaluator in evaluators:
        if evaluator.identifier in evaluator_ids:
            logger.warning(
                f"{evaluator.name} with id {evaluator.identifier} is duplicated. Results will be overwritten"
            )
        else:
            evaluator_ids.add(evaluator.identifier)

    data_dict: dict[str, list[AgentDataPoint]] = defaultdict(list)

    evaluation_results: list[EvaluationResult] = []
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

    for agent_name in data_dict:

        logger.info(
            f"Evaluating agent: {agent_name} with {len(data_dict[agent_name])} data points."
        )

        evaluator_results: list[EvaluatorResult] = []
        for evaluator in evaluators:
            logger.info(
                f"Running evaluator: {evaluator.__class__.__name__}({str(evaluator.identifier)[:4]}...)"
            )
            result = evaluator.run(data_dict[agent_name])

            evaluator_results.append(result)
            logger.info(
                f"Completed evaluator: {evaluator.__class__.__name__}({str(evaluator.identifier)[:4]}...)"
            )

        evaluation_results.append(
            EvaluationResult(
                evaluation_name=f"{name}" if name else None,
                agent_name=agent_name,
                agent_data_ids=[adp.identifier for adp in data_dict[agent_name]],
                results=evaluator_results,
                metrics=[metric for er in evaluator_results for metric in er.metrics],
            )
        )

    try:
        logger.info("Evaluation run complete.")
        save(evaluation_results)
    except Exception as e:
        logger.error(f"Failed to save evaluation results: {e}")
    return evaluation_results
