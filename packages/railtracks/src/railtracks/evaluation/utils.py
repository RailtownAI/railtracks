import json
from pathlib import Path
from uuid import UUID

from .evaluators.metrics import Metric
from .result import EvaluationResult

EVALS_DIR = Path(".railtracks/data/evaluations")


def save(results: list[EvaluationResult]):
    for result in results:
        save_metrics(set(result.metrics))
        save_evaluator_results(result)


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


def save_evaluator_results(evaluation_result: EvaluationResult):

    folder_name = f"Evaluation(name={evaluation_result.evaluation_name}, Agent={evaluation_result.agent_name}, id={evaluation_result.evaluation_id}"

    evaluation_results_dir = EVALS_DIR / "results" / folder_name
    evaluation_results_dir.mkdir(
        parents=True, exist_ok=False  # the evalution ids should be unique
    )

    agent_run_fp = EVALS_DIR / "results" / folder_name / "agent_runs.json"
    if not agent_run_fp.exists():
        agent_run_fp.write_text(
            json.dumps(
                [str(run_id) for run_id in evaluation_result.agent_run_ids],
                indent=2,
            )
        )

    for evaluator_result in evaluation_result.results:
        fp = evaluation_results_dir / f"{evaluator_result.evaluator_id}.json"
        if fp.exists():
            continue
        else:
            fp.touch()
            fp.write_text(
                json.dumps(
                    evaluator_result.model_dump(mode="json", exclude={"metrics"}),
                    indent=2,
                )
            )
