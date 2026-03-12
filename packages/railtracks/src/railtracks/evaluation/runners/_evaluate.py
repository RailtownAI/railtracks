
from collections import defaultdict

from railtracks.evaluation.data.agent_input_dataset import AgentInputDataset
from railtracks.orchestration.flow import Flow
from rich import print
from rich.prompt import Prompt
from datetime import datetime, timezone
from typing import Any, Callable, ParamSpec, TypeVar

from ...utils.logging.create import get_rt_logger
from ..point import AgentDataPoint, create_agent_data_points_from_session_dict
from ..data.evaluation_dataset import EvaluationDataset
from ..evaluators import Evaluator
from ..result import EvaluationResult, EvaluatorResult
from ..utils import save, payload

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


def evaluate(
    data: AgentDataPoint | list[AgentDataPoint] | EvaluationDataset,
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

    logger.info(f"Evaluation DONE.")

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

_P = ParamSpec("_P")
_TOutput = TypeVar("_TOutput")

def run_and_evaluate(
    flow: Flow[_P, _TOutput],
    inputs: AgentInputDataset[_P],
    evaluators: list[Evaluator],
    agent_selection: bool = True,
    agents: list[str] | None = None,
    name: str | None = None,
    payload_callback: Callable[[dict[str, Any]], Any] | None = None,    
):
    agent_data_points = []
    def collect_agent_data_points_from_run(session_dict: dict[str, Any]) -> None:
        agent_data_points.extend(create_agent_data_points_from_session_dict(session_dict))

    
    hooked_flow = flow.update_payload_callback(collect_agent_data_points_from_run)
    input_args = [args for args, kwargs in inputs.input]
    input_kwargs = [kwargs for _, kwargs in inputs.input]

    hooked_flow.batched_run(input_args, input_kwargs)

    return evaluate(
        data=agent_data_points,
        evaluators=evaluators,
        agent_selection=agent_selection,
        agents=agents,
        name=name,
        payload_callback=payload_callback,
    )

    
    

    
