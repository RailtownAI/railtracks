import json
from pathlib import Path
from .result import EvaluationResult
from .evaluators.metrics import Metric

EVALS_DIR = Path(".railtracks/evaluations")

def save(results: list[EvaluationResult]):
    for result in results:
        save_metrics(set(result.metrics))

def save_metrics(metrics: set[Metric]):
    metrics_dir = EVALS_DIR / "metrics"
    metrics_dir.mkdir(
        parents=True, exist_ok=True
    )
    for metric in metrics:
        fp = metrics_dir/f"{metric.identifier}.json"
        if fp.exists():
            continue
        else:
            fp.touch()
            fp.write_text(json.dumps(metric.model_dump(mode="json"), indent=2))  

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

        file_path = (
            evals_dir / f"{result.evaluation_name}_{result.evaluation_id}.json"
        )

        file_path.touch()
        file_path.write_text(json.dumps(result.model_dump(mode="json"), indent=2))