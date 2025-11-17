from datetime import datetime
from pydantic import BaseModel
from railtracks.llm.response import Response
from .evaluators.metrics import Metric
from typing import Any

class EvaluationResult(BaseModel):
    """Result of evaluating an agent on a single input."""
    
    eval_id: str
    agent_name: str
    agent_response: Response
    metrics: list[Metric]
    evaluator_outputs: dict[str, Any]
    timestamp: datetime
    input_data: str
    expected_output: str | None = None