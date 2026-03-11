from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Callable

from rich import print
from rich.prompt import Prompt

from ...utils.logging.create import get_rt_logger
from ..evaluators import Evaluator
from ..point import AgentDataPoint
from ..result import EvaluationResult, EvaluatorResult
from ..utils import payload, save

logger = get_rt_logger("evaluate")

# Color scheme for agent selection UI
COLORS = {
    "header": "bold cyan",
    "index": "bold yellow",
    "agent_name": "green",
    "prompt": "bold magenta",
    "highlight": "bold red",
    "success": "bold green",
    "error": "bold red",
    "selected": "cyan",
}


def _select_agent(agents: dict[str, int]) -> list[str]:
    print(
        f"\n[{COLORS['header']}]Multiple agents found in the data:[/{COLORS['header']}]"
    )
    for i, agent_name in enumerate(agents.keys()):
        print(
            f"  [{COLORS['index']}]{i}[/{COLORS['index']}]: [{COLORS['agent_name']}]{agent_name}[/{COLORS['agent_name']}] -> {agents[agent_name]} data points"
        )
    user_input = Prompt.ask(
        f"\n[{COLORS['prompt']}]Select agent index(es)[/{COLORS['prompt']}] (comma-separated), or [{COLORS['highlight']}]-1[/{COLORS['highlight']}] to evaluate all"
    )

    if user_input.strip() == "-1":
        print(f"[{COLORS['success']}]✓[/{COLORS['success']}] Evaluating all agents")
        return list(agents.keys())

    try:
        indices = [int(idx.strip()) for idx in user_input.split(",")]
        selected = [
            list(agents.keys())[idx] for idx in indices if 0 <= idx < len(agents)
        ]
        selected_color = COLORS["selected"]
        selected_str = ", ".join(
            f"[{selected_color}]{agent}[/{selected_color}]" for agent in selected
        )
        print(f"[{COLORS['success']}]✓[/{COLORS['success']}] Selected: {selected_str}")
        return selected
    except (ValueError, IndexError):
        print(
            f"[{COLORS['error']}]✗[/{COLORS['error']}] Invalid input. Evaluating all agents."
        )
        return list(agents.keys())


def _check_evaluators(evaluators: list[Evaluator]) -> None:
    """Warn if any evaluators share the same identifier.

    Args:
        evaluators: The list of Evaluator instances to validate.
    """
    evaluator_ids: set[str] = set()
    for evaluator in evaluators:
        if evaluator.identifier in evaluator_ids:
            logger.warning(
                f"{evaluator.name} with id {evaluator.identifier} is duplicated. Results will be overwritten"
            )
        else:
            evaluator_ids.add(evaluator.identifier)


def _setup_agent_data(
    data: AgentDataPoint | list[AgentDataPoint],
    agent_selection: bool,
    agents: list[str] | None,
) -> tuple[dict[str, list[AgentDataPoint]], list[str]]:
    """Build the agent-to-data-points mapping and resolve which agents to evaluate.

    Args:
        data: A single AgentDataPoint or a list of AgentDataPoints to organise.
        agent_selection: When True and multiple agents are present, prompts the user
            interactively to pick which agents to evaluate.
        agents: An explicit list of agent names to evaluate. Overrides
            ``agent_selection`` when provided; agents not present in the data are
            silently skipped with a warning.

    Returns:
        A tuple of ``(data_dict, agents)`` where ``data_dict`` maps each agent name
        to its list of AgentDataPoints and ``agents`` is the resolved list of agent
        names to evaluate.

    Raises:
        ValueError: If ``data`` is not an AgentDataPoint or a list of AgentDataPoints.
    """
    data_dict: dict[str, list[AgentDataPoint]] = defaultdict(list)

    if isinstance(data, list):
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

    if agents is not None:
        for agent in agents:
            if agent not in data_dict:
                logger.warning(f"Agent {agent} not found in data. Skipping.")
        agents = [agent for agent in agents if agent in data_dict]
    elif agent_selection and len(data_dict) > 1:
        agents = _select_agent(
            {agent_name: len(data_dict[agent_name]) for agent_name in data_dict.keys()}
        )
    else:
        agents = list(data_dict.keys())

    return data_dict, agents


def evaluate(
    data: AgentDataPoint | list[AgentDataPoint],
    evaluators: list[Evaluator],
    agent_selection: bool = True,
    agents: list[str] | None = None,
    name: str | None = None,
    payload_callback: Callable[[dict[str, Any]], Any] | None = None,
):
    """Evaluate agent data using the provided evaluators.

    Args:
        data: The agent data to be evaluated. Can be a single AgentDataPoint, a list of AgentDataPoints, or an EvaluationDataset.
        evaluators: A list of Evaluator instances to run on the data.
        agent_selection: If True and multiple agents are found in the data, prompts the user to select which agents to evaluate.
                         If False, evaluates all agents without prompting.
        agents: An optional list of agent names to evaluate. If provided, only these agents will be evaluated. Overrides agent_selection if both are provided.
        name: An optional name for the evaluation, which will be included in the EvaluationResult.
        payload_callback: An optional callback function that will be called with the evaluation results payload after evaluation is complete. Can be used for custom logging, notifications, etc.
    Returns:
        A list of EvaluationResult instances containing the results from each evaluator.
    """
    _check_evaluators(evaluators)

    data_dict, agents = _setup_agent_data(data, agent_selection, agents)

    evaluation_results: list[EvaluationResult] = []

    for agent_name in agents:
        logger.info(
            f"Evaluation for {agent_name} with {len(data_dict[agent_name])} data points CREATED"
        )

        evaluator_results: list[EvaluatorResult] = []

        start_time = datetime.now(timezone.utc)
        for evaluator in evaluators:
            logger.info(f"Evaluator: {evaluator.__class__.__name__} CREATED")
            try:
                result = evaluator.run(data_dict[agent_name])
            except Exception as e:
                logger.error(f"Evaluator {evaluator.__class__.__name__} FAILED: {e}")
                continue

            evaluator_results.append(result)
            logger.info(f"Evaluator: {evaluator.__class__.__name__} DONE")

        logger.info(f"Evaluation for {agent_name} DONE.")

        metrics_map = {}
        for er in evaluator_results:
            metrics = er.metrics
            for metric in metrics:
                metrics_map[metric.identifier] = metric

        end_time = datetime.now(timezone.utc)

        evaluation_results.append(
            EvaluationResult(
                evaluation_name=name or None,
                created_at=start_time,
                completed_at=end_time,
                agents=[
                    {
                        "agent_name": agent_name,
                        "agent_node_ids": [
                            {
                                "session_id": adp.session_id,
                                "agent_node_id": adp.identifier,
                            }
                            for adp in data_dict[agent_name]
                        ],
                    }
                ],
                metrics_map=metrics_map,
                evaluator_results=evaluator_results,
            )
        )

    logger.info("Evaluation DONE.")

    if payload_callback is not None:
        try:
            for result in evaluation_results:
                payload_callback(payload(result))
        except Exception as e:
            logger.error(f"Failed to execute payload callback: {e}")

    try:
        save(evaluation_results)
    except Exception as e:
        logger.error(f"Failed to save evaluation results: {e}")
    return evaluation_results
