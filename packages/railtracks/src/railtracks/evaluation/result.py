from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, Field
from .evaluators.metrics import Metric, Numerical, Categorical

class AgentRun(BaseModel):
    session_id: UUID
    run_id: UUID

class MetricResult(BaseModel):
    metric: Metric
    value: str | float | int

class EvaluatorResult(BaseModel):
    name: str
    evaluator_id: UUID
    results: dict[str, list[Metric]]
    
class EvaluationResult(BaseModel):    
    evaluation_id: UUID
    evaluation_name: str
    agent_name: str
    created_at: datetime
    agent_run_ids: list[UUID] = Field(default_factory=list, description="If applicable, list of agent run UUIDs that were part of this evaluation")
    data_points: list[UUID] = Field(default_factory=list, description="If applicable, list of data point UUIDs that were evaluated")
    results: list[EvaluatorResult]
    metrics: list[Metric]
