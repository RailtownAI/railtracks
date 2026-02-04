import json
from pathlib import Path
from .result import EvaluationResult, EvaluatorResult
from .evaluators.metrics import Metric
from uuid import UUID

EVALS_DIR = Path(".railtracks/evaluations")


def save(results: list[EvaluationResult]):
    for result in results:
        save_metrics(set(result.metrics))
        save_evaluator_results(result.evaluation_id, result.results)
        save_agent_runs(result.evaluation_id, result.agent_run_ids)

def save_agent_runs(evaluation_id: UUID, agent_runs: list):
    fp = EVALS_DIR / "results" / f"{evaluation_id}" / "agent_runs.json"
    fp.write_text(
        json.dumps(
            [str(run_id) for run_id in agent_runs],
            indent=2,
        )
    )

def save_metrics(metrics: set[Metric]):
    metrics_dir = EVALS_DIR / "metrics"
    metrics_dir.mkdir(parents=True, exist_ok=True)
    for metric in metrics:
        fp = metrics_dir / f"{metric.identifier}.json"
        if fp.exists():
            continue
        else:
            fp.touch()
            fp.write_text(json.dumps(metric.model_dump(mode="json"), indent=2))


def save_evaluator_results(
    evaluation_id: UUID, evaluator_results: list[EvaluatorResult]
):
    evaluator_results_dir = EVALS_DIR / "results" / f"{evaluation_id}"
    evaluator_results_dir.mkdir(
        parents=True, exist_ok=False  # the evalution ids should be unique
    )

    for evaluator_result in evaluator_results:
        eval_name_dir = evaluator_results_dir / evaluator_result.evaluator_name
        eval_name_dir.mkdir(parents=True, exist_ok=True)
        fp = eval_name_dir / f"{evaluator_result.evaluator_id}.json"
        if fp.exists():
            continue
        else:
            fp.write_text(
                json.dumps(
                    evaluator_result.model_dump(
                        mode="json", exclude={"metrics"}
                    ),
                    indent=2,
                )
            )


def save_evaluation_results(results: list[EvaluationResult]):
    """Saves evaluation results to a specified file.

    Args:
        results (dict): A dictionary containing evaluation results.
        filepath (str): The path to the file where results will be saved.
    """
    railtracks_dir = Path(".railtracks")
    evals_dir = railtracks_dir / "evaluations" / "results"
    evals_dir.mkdir(
        parents=True, exist_ok=True
    )  # Creates directory structure if doesn't exist, skips otherwise.

    for result in results:

        file_path = evals_dir / f"{result.evaluation_name}_{result.evaluation_id}.json"

        file_path.touch()
        file_path.write_text(json.dumps(result.model_dump(mode="json"), indent=2))
