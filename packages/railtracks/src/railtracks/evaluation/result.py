from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, Field
from .evaluators.metrics import Metric, Numerical, Categorical

class AgentRun(BaseModel):
    session_id: UUID
    run_id: UUID

class MetricResult(BaseModel):
    metric_name: str
    metric_id: UUID
    value: str | float | int

class EvaluatorResult(BaseModel):
    evaluator_name: str
    agent_name: str
    evaluator_id: UUID
    metrics: list[Metric]
    results: list[tuple[UUID, MetricResult]] | list[MetricResult]
    
class EvaluationResult(BaseModel):    
    evaluation_id: UUID
    evaluation_name: str
    agent_name: str
    created_at: datetime
    agent_run_ids: list[UUID] = Field(default_factory=list, description="If applicable, list of agent run UUIDs that were part of this evaluation")
    data_points: list[UUID] = Field(default_factory=list, description="If applicable, list of data point UUIDs that were evaluated")
    results: list[EvaluatorResult]
    metrics: list[Metric]
