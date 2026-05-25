import json
from typing import Any

from railtracks.paths import resolve_railtracks_home

from .result import EvaluationResult


def payload(evaluation_result: EvaluationResult) -> dict[str, Any]:
    """Convert an EvaluationResult to a JSON-serializable dictionary."""
    return evaluation_result.model_dump(mode="json")


def save(results: list[EvaluationResult]):
    """Save evaluation results to disk."""
    evals_dir = resolve_railtracks_home() / "data" / "evaluations"
    for result in results:
        fp = evals_dir / f"{result.evaluation_id}.json"
        fp.parent.mkdir(parents=True, exist_ok=True)
        if fp.exists():
            raise Exception(
                f"Evaluation result with id {result.evaluation_id} already exists."
            )
        fp.write_text(json.dumps(payload(result)))
