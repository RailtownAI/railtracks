import json
from pathlib import Path
from typing import Any

from .result import EvaluationResult

EVALS_DIR = Path(".railtracks/data/evaluations")

def payload(evaluation_result: EvaluationResult) -> dict[str, Any]:
    """Convert an EvaluationResult to a JSON-serializable dictionary."""
    return evaluation_result.model_dump(mode="json")

def save(results: list[EvaluationResult]):
    """Save evaluation results to disk."""
    for result in results:
        fp = EVALS_DIR / f"{result.evaluation_id}.json"
        fp.parent.mkdir(parents=True, exist_ok=True)
        if fp.exists():
            raise Exception(f"Evaluation result with id {result.evaluation_id} already exists.")
        fp.write_text(json.dumps(payload(result)))