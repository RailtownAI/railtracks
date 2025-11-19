from datetime import datetime
from uuid import UUID
from pydantic import BaseModel
from railtracks.llm.response import Response
from .evaluators.metrics import Metric
from typing import Any

class MetricOutput(BaseModel):
    name: str

class EvaluatorResult(BaseModel):
    metric_outputs: list[Metric]

class EvaluatorRun(BaseModel):
    name: str
    evaluator_id: UUID
    config_hash: int

    result: list[EvaluatorResult]
    
class EvaluationResult(BaseModel):    
    evaluation_id: UUID
    evaluation_name: str
    agent_name: str
    created_at: datetime
    runs: list[EvaluatorRun]
    results: list[EvaluatorResult]
    metrics: list[Metric]